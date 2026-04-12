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
3. Apply for message sending permissions as needed (text / image / voice / file)

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

### Step 2: Clone this repo and run the installer

```bash
git clone https://github.com/shynloc/Hermes-Agent-QQ-Plugin.git
cd Hermes-Agent-QQ-Plugin
bash install.sh
```

The installer:
- Copies `qq.py` to the Hermes platforms directory
- Installs `qq-botpy` and `pysilk` into the Hermes venv
- Applies all required patches to Hermes core files (idempotent — safe to re-run after `git pull`)

### Step 3: Configure credentials

Add to `~/.hermes/.env`:

```env
QQ_APP_ID=your_app_id
QQ_APP_SECRET=your_app_secret
QQ_ALLOW_ALL_USERS=false  # set to true to allow all QQ users
```

### Step 4: Enable the platform

Add to `~/.hermes/config.yaml`:

```yaml
platforms:
  qq:
    enabled: true

platform_toolsets:
  qq:
  - hermes-telegram
```

### Step 5: Restart the Gateway

```bash
hermes gateway restart
```

### Re-running after `hermes pull` / Hermes updates

The installer patches Hermes core files which are overwritten by updates. Simply re-run:

```bash
bash install.sh
```

All patches are idempotent — already-applied changes are skipped automatically.

---

## Linux systemd Setup

> **Note:** `hermes gateway install` sets up the service automatically and is the recommended approach. Use the manual template below only if you need a custom setup.

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

For more detailed troubleshooting including `KeyError: 'qq'`, `ModuleNotFoundError: No module named 'botpy'`, and post-`git pull` breakage, see **[TROUBLESHOOTING.md](./TROUBLESHOOTING.md)**.

---

## Related Projects

- [Hermes Agent](https://github.com/NousResearch/hermes-agent)
- [qq-botpy](https://github.com/tencent-connect/botpy)
- [openclaw-qqbot](https://github.com/openclaw/openclaw-qqbot) — chunked upload protocol reference

---

## License

MIT
