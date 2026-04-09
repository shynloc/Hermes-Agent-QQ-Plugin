# Hermes Agent QQ Plugin

> Connect [Hermes Agent](https://github.com/NousResearch/hermes-agent) to QQ using the **official QQ Bot Open Platform API**.  
> No NapCat or go-cqhttp required — fully compliant and stable.

English | [中文](./README.zh.md)

---

## Features

| Type | C2C (DM) | Group (@ mention) | Guild |
|------|:--------:|:-----------------:|:-----:|
| Text | ✅ | ✅ | ✅ |
| Voice | ✅ | ✅ | — |
| Image | ✅ | ✅ | ✅ |
| File | ✅ | ✅ | — |

- Voice auto-conversion: OGG / MP3 / WAV → SILK (QQ native format)
- Images support both local paths and HTTP URLs
- Files support any format (.md / .pdf / .docx / .xlsx, etc.)
- Long messages are automatically split (> 5000 chars)

---

## Requirements

| Dependency | Version | Notes |
|------------|---------|-------|
| [Hermes Agent](https://github.com/NousResearch/hermes-agent) | v0.8.0+ | Main application |
| Python | 3.11+ | Bundled with Hermes |
| ffmpeg | any | Voice format conversion |
| [qq-botpy](https://github.com/tencent-connect/botpy) | 1.2.1+ | Official QQ Bot Python SDK |
| [pysilk](https://pypi.org/project/pysilk/) | any | SILK audio encoding |
| QQ Bot Open Platform account | — | See setup guide below |

---

## QQ Bot Account Setup

1. Go to [QQ Open Platform](https://q.qq.com/) and create a bot
2. Obtain your **AppID** and **AppSecret**
3. Enable the following **Intents** in Developer Settings:
   - `Public Messages` (group @ + C2C)
   - `Guild Messages` (guild @ — optional)
   - `Guild Direct Messages` (guild DM — optional)
4. Apply for message sending permissions as needed (text / image / voice / file)

---

## Installation

### Step 1: Install system dependencies

**macOS**
```bash
brew install ffmpeg
```

**Ubuntu / Debian**
```bash
sudo apt-get install -y ffmpeg
```

### Step 2: Install Python dependencies

```bash
cd ~/.hermes/hermes-agent
venv/bin/pip install qq-botpy pysilk
```

### Step 3: Deploy the plugin

```bash
cp qq.py ~/.hermes/hermes-agent/gateway/platforms/qq.py
```

### Step 4: Configure credentials

Add to `~/.hermes/.env`:

```env
QQ_APP_ID=your_app_id
QQ_APP_SECRET=your_app_secret
QQ_ALLOW_ALL_USERS=true
```

### Step 5: Enable the platform

Add to `~/.hermes/config.yaml` (before the `streaming:` key):

```yaml
platforms:
  qq:
    enabled: true
```

### Step 6: Restart the Gateway

**macOS**
```bash
hermes gateway stop && hermes gateway start
```

**Linux**
```bash
sudo systemctl restart hermes-gateway
# or run in foreground for debugging:
hermes gateway run
```

---

## Linux systemd Setup

```ini
# /etc/systemd/system/hermes-gateway.service
[Unit]
Description=Hermes Agent Gateway
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/home/your_user/.hermes/hermes-agent
ExecStart=/home/your_user/.hermes/hermes-agent/venv/bin/python -m hermes_cli.main gateway run
Restart=on-failure
RestartSec=10
EnvironmentFile=/home/your_user/.hermes/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable hermes-gateway
sudo systemctl start hermes-gateway
```

---

## Configuration Reference

### Environment Variables (`.env`)

| Variable | Required | Description |
|----------|:--------:|-------------|
| `QQ_APP_ID` | ✅ | QQ Bot AppID |
| `QQ_APP_SECRET` | ✅ | QQ Bot AppSecret |
| `QQ_ALLOW_ALL_USERS` | — | Set `true` to allow all users (default: `false`) |

### config.yaml

```yaml
platforms:
  qq:
    enabled: true
```

---

## Troubleshooting

**Connection timeout (60s `_ready` event timeout)**  
Verify your AppID / AppSecret. Make sure the bot status is "Online" in QQ Open Platform.

**Voice send fails**  
Confirm ffmpeg is installed (`ffmpeg -version`) and pysilk is installed (`python -c "import pysilk"`).

**Upload returns error 40093002**  
Daily upload quota exceeded. Retry the next day.

**High latency from overseas servers**  
`api.sgroup.qq.com` and `bots.qq.com` are hosted in mainland China. Overseas access works but may be slow. Configure a proxy if needed.

---

## Related Projects

- [Hermes Agent](https://github.com/NousResearch/hermes-agent)
- [qq-botpy](https://github.com/tencent-connect/botpy)
- [openclaw-qqbot](https://github.com/openclaw/openclaw-qqbot) — chunked upload protocol reference

---

## License

MIT
