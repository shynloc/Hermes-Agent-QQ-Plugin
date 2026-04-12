# Hermes Agent QQ 插件

> 基于 QQ Bot **官方开放平台 API**，让 Hermes Agent 通过 QQ 与你双向沟通。  
> 无需 NapCat / go-cqhttp 等第三方框架，合规稳定。

[English](./README.md) | 中文

---

## 功能

| 类型 | C2C 私聊 | 群聊（@机器人） | 频道 |
|------|:--------:|:-------------:|:----:|
| 文字消息 | ✅ | ✅ | ✅ |
| 语音消息 | ✅ | ✅ | — |
| 图片消息 | ✅ | ✅ | ✅ |
| 文件发送 | ✅ | ✅ | — |

- 语音自动转换：OGG / MP3 / WAV → SILK（QQ 原生格式）
- 图片支持本地文件和 HTTP URL 两种来源
- 文件支持任意格式（.md / .pdf / .docx / .xlsx 等）
- 长消息自动拆分（超过 5000 字符）

---

## 前置要求

| 依赖 | 版本要求 | 说明 |
|------|---------|------|
| [Hermes Agent](https://github.com/NousResearch/hermes-agent) | v0.8.0+ | 主程序 |
| Python | 3.11+ | 随 Hermes 附带 |
| ffmpeg | 任意版本 | 语音格式转换 |
| [qq-botpy](https://github.com/tencent-connect/botpy) | 1.2.1+ | QQ Bot Python SDK |
| [pysilk](https://pypi.org/project/pysilk/) | 任意版本 | SILK 编码 |
| QQ Bot 开放平台账号 | — | 见下方申请指引 |

---

## 申请 QQ Bot 账号

1. 前往 [QQ 开放平台](https://q.qq.com/) 注册并创建机器人
2. 获取 **AppID** 和 **AppSecret**
3. 在「功能配置」中申请以下能力（如需）：
   - 发送消息（文字/图片/语音/文件）

---

## 安装步骤

### 第一步：安装系统依赖

**macOS**
```bash
brew install ffmpeg
```

**Ubuntu / Debian**
```bash
sudo apt-get install -y ffmpeg
```

**CentOS / RHEL**
```bash
sudo yum install -y ffmpeg
```

### 第二步：安装 Python 依赖

Hermes 使用 `uv` 管理虚拟环境，需将依赖安装到 Hermes 自带的 venv 中：

```bash
uv pip install qq-botpy pysilk --python ~/.hermes/hermes-agent/venv/bin/python3
```

### 第三步：部署插件文件

直接下载到 Hermes Agent 的平台适配器目录：

```bash
curl -fsSL https://raw.githubusercontent.com/shynloc/Hermes-Agent-QQ-Plugin/main/qq.py \
  -o ~/.hermes/hermes-agent/gateway/platforms/qq.py
```

### 第四步：配置环境变量

在 `~/.hermes/.env` 中添加：

```env
QQ_APP_ID=你的AppID
QQ_APP_SECRET=你的AppSecret
QQ_ALLOW_ALL_USERS=false  # 设为 true 则对所有 QQ 用户开放
```

### 第五步：启用平台

在 `~/.hermes/config.yaml` 中添加：

```yaml
platforms:
  qq:
    enabled: true
```

### 第六步：重启 Gateway

**macOS（launchd）**
```bash
hermes gateway stop && hermes gateway start
```

**Linux（systemd）**
```bash
systemctl --user restart hermes-gateway
# 或者前台运行调试：
hermes gateway run
```

---

## Linux systemd 配置参考

> **说明：** 推荐直接使用 `hermes gateway install` 自动注册服务。以下模板仅供需要自定义配置时参考。

```ini
# ~/.config/systemd/user/hermes-gateway.service
[Unit]
Description=Hermes Agent Gateway
After=network.target

[Service]
Type=simple
WorkingDirectory=%h/.hermes/hermes-agent
ExecStart=%h/.local/bin/hermes gateway run
Restart=on-failure
RestartSec=10
EnvironmentFile=%h/.hermes/.env

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable hermes-gateway
systemctl --user start hermes-gateway
```

---

## 配置参考

### 环境变量（`.env`）

| 变量名 | 必填 | 说明 |
|--------|:----:|------|
| `QQ_APP_ID` | ✅ | QQ Bot AppID |
| `QQ_APP_SECRET` | ✅ | QQ Bot AppSecret |
| `QQ_ALLOW_ALL_USERS` | — | `true` 开放给所有用户，默认 `false` |

### config.yaml

```yaml
platforms:
  qq:
    enabled: true
```

---

## 故障排查

**Q: 连接超时，`_ready` event 60 秒后报错**  
A: 检查 AppID / AppSecret 是否正确；确认 QQ Bot 开放平台中机器人状态为「已上线」。

**Q: 语音发送失败**  
A: 确认 ffmpeg 已安装（`ffmpeg -version`）；确认 pysilk 已安装（`python -c "import pysilk"`）。

**Q: 图片 / 文件上传返回 40093002**  
A: 已超出每日累计上传限额，次日重试。

**Q: 消息发送返回 `msg_seq` 重复错误**  
A: 重启 Gateway 重置序列号即可。

**Q: 海外服务器连接 QQ API 延迟高**  
A: `api.sgroup.qq.com` 和 `bots.qq.com` 均为境内服务器，海外访问有延迟但可达。如需加速可配置代理，并将这两个域名加入代理白名单。

更多详细问题排查（包括 `KeyError: 'qq'`、`ModuleNotFoundError: No module named 'botpy'`、`git pull` 后插件失效等），请参阅 **[TROUBLESHOOTING.zh.md](./TROUBLESHOOTING.zh.md)**。

---

## 相关项目

- [Hermes Agent](https://github.com/NousResearch/hermes-agent) — 主程序
- [qq-botpy](https://github.com/tencent-connect/botpy) — QQ Bot 官方 Python SDK
- [openclaw-qqbot](https://github.com/openclaw/openclaw-qqbot) — 分片上传协议参考来源

---

## License

MIT
