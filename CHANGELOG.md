# Changelog

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
