# Changelog

## v1.2.1 (2026-04-14)

### 修复

- **`install.sh` Step 5 兼容新版 Hermes**：Hermes 新版本将 `PLATFORMS` 注册表从 `hermes_cli/tools_config.py` 迁移到独立的 `hermes_cli/platforms.py`，导致 Step 5 锚点失效并显示 `[WARN] anchor not found`。现在自动检测文件位置，优先打 `platforms.py`，旧版本回退到 `tools_config.py`。

---

## v1.2.0 (2026-04-13)

### 新增

- **QQ 文件附件接收**：`qq.py` 新增 `_handle_message_with_attachments`，正确处理用户通过 QQ 发送的图片、音频、文档等附件
  - 自动下载并缓存附件（图片 / 音频 / 文档分别路由到对应缓存目录）
  - 处理协议相对 URL（`//gchat.qpic.cn/...` → `https://...`）
  - 文档类附件无标题时，自动注入中文 context note，避免中文优先模型（如 doubao）因 session 历史污染而忽略文件

### 修复

- 修复 QQ 发送文件后机器人回复"没有收到文件"的问题（附件字段 `message.attachments` 从未被读取）

### 文档

- TROUBLESHOOTING（中英）新增"发送文件后机器人说没有收到"Q&A 条目

---

## v1.1.0 (2026-04-12)

### 新增

- **`install.sh` 一键安装脚本**：自动完成 qq.py 部署、Python 依赖安装、以及所有 Hermes 核心文件补丁，无需手动修改任何框架代码
- **幂等安装**：`install.sh` 可在 Hermes 更新（`git pull`）后重复运行，已应用的补丁自动跳过
- **TROUBLESHOOTING.md / TROUBLESHOOTING.zh.md**：基于多台机器真实部署经验整理的完整故障排查文档（中英双语）

### 修复

- 补全 `gateway/config.py` 中 `Platform` 枚举缺少 `QQ = "qq"` 的问题（导致 QQ 平台无法被识别）
- 补全 `gateway/config.py` 中 `get_connected_platforms()` 缺少 QQ 校验（导致启动提示 `No messaging platforms enabled`）
- 补全 `gateway/config.py` 中 `_apply_env_overrides()` 缺少 QQ 环境变量加载（导致 `.env` 中的 QQ 配置不生效）
- 补全 `gateway/run.py` 中 `_create_adapter()` 缺少 QQ 适配器加载分支
- 补全 `gateway/run.py` 中权限映射表缺少 QQ 条目（`QQ_ALLOWED_USERS` / `QQ_ALLOW_ALL_USERS`）
- 补全 `hermes_cli/tools_config.py` 中 `PLATFORMS` 字典缺少 `qq` 条目（导致收消息时 `KeyError: 'qq'`）
- 补全 `toolsets.py` 中缺少 `hermes-qq` 工具集定义及 `hermes-gateway` includes 注册

### 文档

- README（中英）安装步骤改为以 `install.sh` 为主流程，大幅简化配置
- Configuration Reference 补充 `platform_toolsets` 配置和 `QQ_ALLOWED_USERS`、`QQ_HOME_CHANNEL` 环境变量说明

---

## v1.0.0 (2026-04-10)

首次发布。

### 新增功能

- **文字消息**：支持 C2C（私聊）、群聊（@机器人）、频道消息收发
- **语音消息**：本地 OGG/MP3/WAV → SILK 转换，通过分片上传协议发送
- **图片消息**：支持本地文件（分片上传）和 HTTP URL 两种来源
- **文件发送**：支持任意格式文件（.md/.pdf/.docx/.xlsx 等）通过分片上传发送
- **长消息分割**：超过 5000 字符自动拆分多条发送
- **msg_seq 自动递增**：避免重复消息报错

### 技术说明

- 基于 QQ Bot 开放平台官方 API（非 NapCat / go-cqhttp）
- 分片上传协议参考 [openclaw-qqbot](https://github.com/openclaw/openclaw-qqbot) 官方实现
- 兼容 Hermes Agent v0.8.0+
