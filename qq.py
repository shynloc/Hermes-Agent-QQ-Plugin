import asyncio
import hashlib
import logging
import os
import subprocess
import tempfile
import time
from typing import Optional, Dict, Any
import aiohttp
import botpy
from botpy.message import Message, DirectMessage, GroupMessage, C2CMessage
from .base import BasePlatformAdapter, MessageEvent, MessageType, SendResult, Platform

logger = logging.getLogger(__name__)
MAX_MESSAGE_LENGTH = 5000
QQ_API_BASE = "https://api.sgroup.qq.com"


class QQAdapter(BasePlatformAdapter):
    def __init__(self, config):
        super().__init__(config, Platform.QQ)
        extra = config.extra or {}
        self.app_id = str(extra.get("app_id") or os.getenv("QQ_APP_ID", "")).strip()
        self.app_secret = str(extra.get("app_secret") or os.getenv("QQ_APP_SECRET", "")).strip()
        self.bot = None
        self.client = None
        self._ready = asyncio.Event()
        self._msg_seq = int(time.time())

    def _next_seq(self) -> int:
        self._msg_seq += 1
        return self._msg_seq

    async def connect(self) -> bool:
        try:
            intents = botpy.Intents(public_guild_messages=True, direct_message=True, public_messages=True)
            self.client = QQClient(intents=intents, adapter=self)

            async def _run_and_propagate():
                try:
                    await self.client.start(appid=self.app_id, secret=self.app_secret)
                except Exception as e:
                    logger.error(f"[QQ] botpy client error: {e}")
                    self._start_error = e
                    self._ready.set()

            self._start_error = None
            self._start_task = asyncio.create_task(_run_and_propagate())
            await asyncio.wait_for(self._ready.wait(), timeout=60)

            if self._start_error:
                raise self._start_error

            logger.info("[QQ] Connected successfully")
            return True
        except Exception as e:
            logger.error(f"[QQ] Connection failed: {str(e)}")
            return False

    async def disconnect(self):
        if self.client:
            await self.client.close()
        self._ready.clear()
        logger.info("[QQ] Disconnected")

    async def send(self, chat_id: str, content: str, reply_to: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> SendResult:
        try:
            if len(content) > MAX_MESSAGE_LENGTH:
                chunks = [content[i:i+MAX_MESSAGE_LENGTH] for i in range(0, len(content), MAX_MESSAGE_LENGTH)]
                results = []
                for chunk in chunks:
                    res = await self._send_single(chat_id, chunk)
                    results.append(res)
                return results[-1]
            return await self._send_single(chat_id, content)
        except Exception as e:
            logger.error(f"[QQ] Send failed: {str(e)}")
            return SendResult(success=False, error=str(e))

    async def _send_single(self, chat_id: str, text: str, **kwargs) -> SendResult:
        try:
            if chat_id.startswith("c2c:"):
                user_openid = chat_id.split(":", 1)[1]
                msg = await self.client.api.post_c2c_message(
                    openid=user_openid,
                    msg_type=0,
                    content=text,
                    msg_seq=self._next_seq()
                )
            elif chat_id.startswith("group:"):
                group_openid = chat_id.split(":", 1)[1]
                msg = await self.client.api.post_group_message(
                    group_openid=group_openid,
                    msg_type=0,
                    content=text,
                    msg_seq=self._next_seq()
                )
            else:
                # 频道消息
                msg = await self.client.api.post_message(channel_id=chat_id, content=text)
            return SendResult(
                success=True,
                message_id=str(msg.get("id", "") if isinstance(msg, dict) else getattr(msg, "id", "")),
                raw_response=msg
            )
        except Exception as e:
            return SendResult(success=False, error=str(e))

    async def send_typing(self, chat_id: str, **kwargs):
        pass

    async def _get_auth_headers(self) -> dict:
        """Get authorization headers with fresh access token."""
        await self.client.http._token.check_token()
        token = self.client.http._token
        return {
            "Authorization": f"QQBot {token.access_token}",
            "X-Union-Appid": self.app_id,
            "Content-Type": "application/json",
        }

    async def _upload_media_chunked(
        self,
        target_id: str,
        file_data: bytes,
        file_type: int,
        file_name: str,
        is_group: bool = False,
    ) -> Optional[str]:
        """
        Upload local media via QQ Bot chunked upload protocol.
        Returns file_info string (for use in media field), or None on failure.
        file_type: 1=image png/jpg, 2=video mp4, 3=voice silk, 4=file (not open)
        Protocol (from QQ Open Platform official source):
          1. POST upload_prepare → {upload_id, block_size, parts[{index, presigned_url}]}
          2. PUT each chunk to COS presigned URL (no auth headers)
          3. POST upload_part_finish for each part → {upload_id, part_index, block_size, md5}
          4. POST /files → {upload_id} → {file_info}
        """
        MD5_10M_SIZE = 10002432  # exactly as defined by QQ Open Platform
        md5_hash = hashlib.md5(file_data).hexdigest()
        sha1_hash = hashlib.sha1(file_data).hexdigest()
        first_segment = file_data[:MD5_10M_SIZE]
        md5_10m = hashlib.md5(first_segment).hexdigest()

        headers = await self._get_auth_headers()

        if is_group:
            prepare_url = f"{QQ_API_BASE}/v2/groups/{target_id}/upload_prepare"
            finish_url  = f"{QQ_API_BASE}/v2/groups/{target_id}/upload_part_finish"
            files_url   = f"{QQ_API_BASE}/v2/groups/{target_id}/files"
        else:
            prepare_url = f"{QQ_API_BASE}/v2/users/{target_id}/upload_prepare"
            finish_url  = f"{QQ_API_BASE}/v2/users/{target_id}/upload_part_finish"
            files_url   = f"{QQ_API_BASE}/v2/users/{target_id}/files"

        async with aiohttp.ClientSession() as session:
            # Step 1: upload_prepare
            prepare_body = {
                "file_type": file_type,
                "file_size": len(file_data),
                "file_name": file_name,
                "md5": md5_hash,
                "sha1": sha1_hash,
                "md5_10m": md5_10m,
            }
            async with session.post(prepare_url, headers=headers, json=prepare_body) as resp:
                prepare_data = await resp.json(content_type=None)
            logger.debug(f"[QQ] upload_prepare response: {prepare_data}")

            if "upload_id" not in prepare_data:
                logger.error(f"[QQ] upload_prepare failed: {prepare_data}")
                return None

            upload_id = prepare_data["upload_id"]
            block_size = int(prepare_data["block_size"])
            parts = prepare_data.get("parts", [])

            # Step 2 & 3: PUT each chunk to COS, then notify finish
            for part in parts:
                part_index = part["index"]  # 1-based
                cos_url = part["presigned_url"]
                offset = (part_index - 1) * block_size
                chunk = file_data[offset: offset + block_size]
                chunk_md5 = hashlib.md5(chunk).hexdigest()

                # PUT to COS (no auth headers — pre-signed URL)
                async with session.put(
                    cos_url, data=chunk,
                    headers={"Content-Length": str(len(chunk))},
                ) as cos_resp:
                    if cos_resp.status not in (200, 204):
                        body = await cos_resp.text()
                        logger.error(f"[QQ] COS PUT part {part_index} failed {cos_resp.status}: {body[:200]}")
                        return None
                    logger.debug(f"[QQ] COS PUT part {part_index}: {cos_resp.status}")

                # upload_part_finish
                finish_body = {
                    "upload_id": upload_id,
                    "part_index": part_index,
                    "block_size": len(chunk),
                    "md5": chunk_md5,
                }
                async with session.post(finish_url, headers=headers, json=finish_body) as resp:
                    finish_data = await resp.json(content_type=None)
                logger.debug(f"[QQ] upload_part_finish part {part_index}: {finish_data}")

            # Step 4: complete upload → get file_info
            files_body = {"upload_id": upload_id}
            async with session.post(files_url, headers=headers, json=files_body) as resp:
                files_data = await resp.json(content_type=None)
            logger.debug(f"[QQ] files complete response: {files_data}")

            file_info = files_data.get("file_info")
            if not file_info:
                logger.error(f"[QQ] files endpoint returned no file_info: {files_data}")
                return None

            return file_info

    async def _send_media(self, chat_id: str, file_info: str, caption: Optional[str] = None) -> SendResult:
        """Send a media message (msg_type=7) using a file_info token."""
        media = {"file_info": file_info}
        try:
            if chat_id.startswith("c2c:"):
                user_openid = chat_id.split(":", 1)[1]
                msg = await self.client.api.post_c2c_message(
                    openid=user_openid,
                    msg_type=7,
                    content=caption or "",
                    media=media,
                    msg_seq=self._next_seq(),
                )
            elif chat_id.startswith("group:"):
                group_openid = chat_id.split(":", 1)[1]
                msg = await self.client.api.post_group_message(
                    group_openid=group_openid,
                    msg_type=7,
                    content=caption or "",
                    media=media,
                    msg_seq=self._next_seq(),
                )
            else:
                # 频道不支持富媒体，退回文字
                return await self._send_single(chat_id, caption or "")
            return SendResult(
                success=True,
                message_id=str(msg.get("id", "") if isinstance(msg, dict) else getattr(msg, "id", "")),
                raw_response=msg,
            )
        except Exception as e:
            return SendResult(success=False, error=str(e))

    async def send_voice(
        self,
        chat_id: str,
        audio_path: str,
        caption: Optional[str] = None,
        reply_to: Optional[str] = None,
        **kwargs,
    ) -> SendResult:
        """Convert OGG → PCM → SILK, upload via chunked protocol, send as voice."""
        try:
            silk_data = await asyncio.get_event_loop().run_in_executor(
                None, self._convert_to_silk, audio_path
            )
            if silk_data is None:
                logger.warning("[QQ] SILK conversion failed, falling back to caption")
                if caption:
                    return await self.send(chat_id=chat_id, content=caption)
                return SendResult(success=False, error="SILK conversion failed")

            is_group = chat_id.startswith("group:")
            target_id = chat_id.split(":", 1)[1] if ":" in chat_id else chat_id
            file_name = os.path.basename(audio_path).rsplit(".", 1)[0] + ".silk"

            file_info = await self._upload_media_chunked(
                target_id=target_id,
                file_data=silk_data,
                file_type=3,
                file_name=file_name,
                is_group=is_group,
            )
            if file_info is None:
                logger.warning("[QQ] Voice upload failed, falling back to caption")
                if caption:
                    return await self.send(chat_id=chat_id, content=caption)
                return SendResult(success=False, error="Voice upload failed")

            return await self._send_media(chat_id, file_info, caption=None)

        except Exception as e:
            logger.error(f"[QQ] send_voice error: {e}")
            if caption:
                return await self.send(chat_id=chat_id, content=caption)
            return SendResult(success=False, error=str(e))

    def _convert_to_silk(self, audio_path: str) -> Optional[bytes]:
        """Synchronously convert audio file to SILK bytes (OGG/MP3/WAV → PCM → SILK)."""
        try:
            import pysilk
        except ImportError:
            logger.error("[QQ] pysilk not installed: pip install pysilk")
            return None

        with tempfile.NamedTemporaryFile(suffix=".pcm", delete=False) as pcm_file:
            pcm_path = pcm_file.name

        try:
            # Convert to 24000 Hz mono 16-bit PCM
            result = subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", audio_path,
                    "-f", "s16le",
                    "-ar", "24000",
                    "-ac", "1",
                    pcm_path,
                ],
                capture_output=True,
                timeout=30,
            )
            if result.returncode != 0:
                logger.error(f"[QQ] ffmpeg failed: {result.stderr.decode()[:200]}")
                return None

            with open(pcm_path, "rb") as f:
                pcm_data = f.read()

            silk_data = pysilk.encode(pcm_data, data_rate=24000, sample_rate=24000)
            logger.info(f"[QQ] SILK conversion: {len(pcm_data)} PCM bytes → {len(silk_data)} SILK bytes")
            return silk_data

        except Exception as e:
            logger.error(f"[QQ] SILK conversion error: {e}")
            return None
        finally:
            try:
                os.unlink(pcm_path)
            except OSError:
                pass

    async def send_document(
        self,
        chat_id: str,
        file_path: str,
        caption: Optional[str] = None,
        file_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        **kwargs,
    ) -> SendResult:
        """Send a file via QQ Bot chunked upload (file_type=4)."""
        try:
            is_group = chat_id.startswith("group:")
            target_id = chat_id.split(":", 1)[1] if ":" in chat_id else chat_id
            display_name = file_name or os.path.basename(file_path)

            with open(file_path, "rb") as f:
                file_data = f.read()

            file_info = await self._upload_media_chunked(
                target_id=target_id,
                file_data=file_data,
                file_type=4,
                file_name=display_name,
                is_group=is_group,
            )
            if file_info:
                return await self._send_media(chat_id, file_info, caption=caption)

            logger.warning(f"[QQ] File upload failed for {file_path}, falling back to text")
        except Exception as e:
            logger.error(f"[QQ] send_document error: {e}")

        # Fallback: send file content for text files, or a notice for binary
        TEXT_EXTENSIONS = {".md", ".txt", ".json", ".yaml", ".yml", ".csv", ".xml",
                           ".toml", ".ini", ".cfg", ".log", ".py", ".js", ".ts",
                           ".html", ".css", ".sh", ".bash"}
        display_name = file_name or os.path.basename(file_path)
        ext = os.path.splitext(file_path)[1].lower()
        if ext in TEXT_EXTENSIONS:
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                if len(content) > 4000:
                    content = content[:4000] + f"\n\n…（内容过长，已截断，共 {len(content)} 字符）"
                header = f"📄 {display_name}\n\n"
                if caption:
                    header = f"{caption}\n{header}"
                return await self.send(chat_id=chat_id, content=header + content, reply_to=reply_to)
            except Exception:
                pass
        notice = f"📎 {display_name}"
        if caption:
            notice = f"{caption}\n{notice}"
        return await self.send(chat_id=chat_id, content=notice, reply_to=reply_to)

    async def send_image_file(
        self,
        chat_id: str,
        image_path: str,
        caption: Optional[str] = None,
        reply_to: Optional[str] = None,
        **kwargs,
    ) -> SendResult:
        """Send a local image file via chunked upload."""
        return await self.send_image(chat_id=chat_id, image_url=image_path, caption=caption)

    async def send_image(self, chat_id: str, image_url: str, caption: Optional[str] = None) -> SendResult:
        """Send image — supports both local file paths and HTTP URLs."""
        try:
            is_group = chat_id.startswith("group:")
            target_id = chat_id.split(":", 1)[1] if ":" in chat_id else chat_id

            if image_url.startswith("http://") or image_url.startswith("https://"):
                # Remote URL: use botpy's post_c2c_file / post_group_file
                if is_group:
                    media = await self.client.api.post_group_file(
                        group_openid=target_id, file_type=1, url=image_url, srv_send_msg=False
                    )
                else:
                    media = await self.client.api.post_c2c_file(
                        openid=target_id, file_type=1, url=image_url, srv_send_msg=False
                    )
                file_info = media.get("file_info") if isinstance(media, dict) else getattr(media, "file_info", None)
            else:
                # Local file: use chunked upload
                with open(image_url, "rb") as f:
                    file_data = f.read()
                ext = os.path.splitext(image_url)[1].lower() or ".jpg"
                file_info = await self._upload_media_chunked(
                    target_id=target_id,
                    file_data=file_data,
                    file_type=1,
                    file_name=os.path.basename(image_url) or f"image{ext}",
                    is_group=is_group,
                )

            if not file_info:
                return SendResult(success=False, error="Image upload failed: no file_info returned")

            return await self._send_media(chat_id, file_info, caption=caption)

        except Exception as e:
            logger.error(f"[QQ] send_image error: {e}")
            return SendResult(success=False, error=str(e))

    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        return {
            "chat_id": chat_id,
            "name": chat_id,
            "type": "direct" if chat_id.startswith("c2c:") else "group"
        }

    def _handle_inbound_message(self, message, is_direct: bool = False, msg_type: str = "guild"):
        try:
            if msg_type == "c2c":
                user_id = getattr(message.author, "user_openid", None) or getattr(message.author, "id", "unknown")
                chat_id = f"c2c:{user_id}"
                username = getattr(message.author, "user_openid", user_id)
            elif msg_type == "group":
                user_id = getattr(message.author, "member_openid", None) or getattr(message.author, "id", "unknown")
                chat_id = f"group:{message.group_openid}"
                username = getattr(message.author, "member_openid", user_id)
            else:
                bot_id = getattr(getattr(self.client, "bot_info", None), "id", None)
                if bot_id and getattr(message.author, "id", None) == bot_id:
                    return
                user_id = message.author.id
                chat_id = f"c2c:{user_id}" if is_direct else message.channel_id
                username = getattr(message.author, "username", user_id)

            source = self.build_source(
                chat_id=chat_id,
                user_id=user_id,
                user_name=username
            )

            event = MessageEvent(
                message_type=MessageType.TEXT,
                text=message.content,
                source=source,
                raw_message=message
            )

            asyncio.create_task(self.handle_message(event))
        except Exception as e:
            logger.error(f"[QQ] Error handling message: {str(e)}")


class QQClient(botpy.Client):
    def __init__(self, intents, adapter: QQAdapter, **kwargs):
        super().__init__(intents=intents, **kwargs)
        self.adapter = adapter

    async def _ready_handler(self, message_event):
        """Override botpy's _ready_handler to set our ready event immediately."""
        result = await super()._ready_handler(message_event)
        logger.info(f"[QQ] Bot ready: {result.get('user', {}).get('username', 'unknown')}")
        self.adapter._ready.set()
        return result

    async def on_ready(self):
        self.adapter._ready.set()

    async def on_at_message_create(self, message: Message):
        self.adapter._handle_inbound_message(message, is_direct=False)

    async def on_direct_message_create(self, message: DirectMessage):
        self.adapter._handle_inbound_message(message, is_direct=True)

    async def on_c2c_message_create(self, message: C2CMessage):
        self.adapter._handle_inbound_message(message, is_direct=True, msg_type="c2c")

    async def on_group_at_message_create(self, message: GroupMessage):
        self.adapter._handle_inbound_message(message, is_direct=False, msg_type="group")


def check_qq_requirements() -> bool:
    try:
        import botpy
        return True
    except ImportError:
        logger.warning("QQ platform requires 'qq-botpy' package, install with: pip install qq-botpy")
        return False
