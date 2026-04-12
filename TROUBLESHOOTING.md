# Troubleshooting & Q&A

This document covers common integration issues when deploying the QQ plugin with Hermes Agent, collected from real debugging sessions across multiple installations.

## Why do so many things break?

Hermes has no plugin auto-discovery mechanism. Adding a new platform requires patching **4–5 core files** in the Hermes source tree. This plugin ships only the adapter (`qq.py`) — the framework registration patches must be applied manually. All the errors below are symptoms of missing patches, not bugs in Hermes itself or user misconfiguration.

---

## Gateway starts with "No messaging platforms enabled"

**Symptom:** After installing the plugin and restarting the gateway, the startup log shows:

```
No messaging platforms enabled
```

QQ never connects and the bot is unreachable.

**Root cause:** Two methods in `gateway/config.py` are missing QQ support:

1. `get_connected_platforms()` — no QQ entry, so QQ is never recognized as a connected platform
2. `_apply_env_overrides()` — QQ env vars (`QQ_APP_ID`, `QQ_APP_SECRET`) are never loaded from `.env` into runtime config

**Fix — `gateway/config.py`, inside `get_connected_platforms()`:** Add after the BlueBubbles check:

```python
elif platform == Platform.QQ and os.getenv("QQ_APP_ID") and os.getenv("QQ_APP_SECRET"):
    connected.append(platform)
```

**Fix — `gateway/config.py`, inside `_apply_env_overrides()`:** Add QQ env loading:

```python
# QQ
qq_app_id = os.getenv("QQ_APP_ID")
qq_app_secret = os.getenv("QQ_APP_SECRET")
if qq_app_id and qq_app_secret:
    if Platform.QQ not in config.platforms:
        config.platforms[Platform.QQ] = PlatformConfig()
    config.platforms[Platform.QQ].enabled = True
    config.platforms[Platform.QQ].extra.update({
        "app_id": qq_app_id,
        "app_secret": qq_app_secret,
        "allow_all_users": os.getenv("QQ_ALLOW_ALL_USERS", "false").lower() in ("true", "1", "yes"),
    })
qq_home = os.getenv("QQ_HOME_CHANNEL")
if qq_home and Platform.QQ in config.platforms:
    config.platforms[Platform.QQ].home_channel = HomeChannel(
        platform=Platform.QQ,
        chat_id=qq_home,
        name=os.getenv("QQ_HOME_CHANNEL_NAME", "Home"),
    )
```

---

## After `git pull` on Hermes Agent, the QQ plugin stops working

**Symptom:** QQ was working before, but after `git pull`, the gateway starts with no QQ connection and no QQ log entries.

**Root cause:** `Platform.QQ` enum value and the QQ adapter loading branch in `run.py` are wiped by every `git pull`.

**Fix — `gateway/config.py`:** Add inside the `Platform` enum (e.g. after `BLUEBUBBLES`):

```python
QQ = "qq"
```

**Fix — `gateway/run.py`:** Add after the BlueBubbles adapter block inside `_create_adapter()`:

```python
elif platform == Platform.QQ:
    from gateway.platforms.qq import QQAdapter, check_qq_requirements
    if not check_qq_requirements():
        logger.warning("QQ: qq-botpy not installed")
        return None
    return QQAdapter(config)
```

---

## `ModuleNotFoundError: No module named 'botpy'` when running `hermes gateway run`

**Symptom:** Running `hermes gateway run` directly crashes with:

```
ModuleNotFoundError: No module named 'botpy'
```

**Root cause:** The `hermes` CLI binary uses **system Python** (`/usr/bin/python3`), but `qq-botpy` is installed in the **Hermes venv** (`~/.hermes/hermes-agent/venv`). Running the CLI directly bypasses the venv.

**Fix:** Always start the gateway through systemd:

```bash
hermes gateway start     # correct — uses venv Python
hermes gateway restart   # correct — uses venv Python
```

If you need to test in the foreground, activate the venv first:

```bash
~/.hermes/hermes-agent/venv/bin/python -m hermes_cli.main gateway run
```

---

## `KeyError: 'qq'` when sending a message to the bot

**Symptom:** The bot receives the message but replies:

```
Sorry, I encountered an error (KeyError).
'qq'
```

**Root cause:** Two missing registrations:

1. `hermes_cli/tools_config.py` — `PLATFORMS` dict has no `qq` entry
2. `~/.hermes/config.yaml` — `platform_toolsets` section has no `qq` entry

**Fix 1 — `hermes_cli/tools_config.py`:** Add inside the `PLATFORMS` dict (after the `weixin` entry):

```python
"qq": {"label": "🐧 QQ", "default_toolset": "hermes-qq"},
```

**Fix 2 — `toolsets.py`:** Add a `hermes-qq` toolset definition:

```python
"hermes-qq": {
    "description": "QQ platform toolset",
    "tools": [],
    "includes": ["hermes-core"]
},
```

Also add `"hermes-qq"` to the `includes` list of the `hermes-gateway` toolset.

**Fix 3 — `~/.hermes/config.yaml`:** Add under `platform_toolsets:`:

```yaml
platform_toolsets:
  qq:
  - hermes-telegram
```

Then restart the gateway:

```bash
hermes gateway restart
```

---

## Missing permission mapping — unauthorized users even after approval

**Symptom:** Messages from approved users are rejected or user authorization doesn't work correctly.

**Root cause:** `gateway/run.py` is missing QQ entries in the permission lookup maps.

**Fix — `gateway/run.py`:** In `platform_env_map`, add:

```python
Platform.QQ: "QQ_ALLOWED_USERS",
```

In `platform_allow_all_map`, add:

```python
Platform.QQ: "QQ_ALLOW_ALL_USERS",
```

---

## Bot says "Hi~ I don't recognize you yet!" — Pairing flow

**Symptom:** When `QQ_ALLOW_ALL_USERS=false`, new users see:

```
Hi~ I don't recognize you yet!
Here's your pairing code: XXXXXXXX
Ask the bot owner to run:
hermes pairing approve qq XXXXXXXX
```

**Fix:** Run on the server:

```bash
hermes pairing approve qq <CODE>
```

The user will be recognized automatically on their next message. This is expected behavior.

---

## Bot responds with "No home channel is set for Qq"

**Symptom:** After the first message, the bot says:

```
📬 No home channel is set for Qq.
Type /sethome to make this chat your home channel, or ignore to skip.
```

**This is not an error.** Type `/sethome` to confirm, or ignore if you don't use cron jobs.

---

## Environment variables in `~/.hermes/.env` not loaded

**Symptom:** `QQ_APP_ID` is set in `.env` but the gateway doesn't pick it up when run manually.

**Root cause:** Hermes does **not** automatically source `~/.hermes/.env` when you run it from the terminal. The env file is only loaded by systemd via the `EnvironmentFile=` directive in the service unit.

**Fix:** Either always start the gateway through systemd (`hermes gateway start`), or source the file manually before running:

```bash
set -a && source ~/.hermes/.env && set +a
hermes gateway run
```

---

## Complete patch checklist (apply after every `git pull`)

| File | Change |
|------|--------|
| `gateway/config.py` | Add `QQ = "qq"` to `Platform` enum |
| `gateway/config.py` | Add QQ check to `get_connected_platforms()` |
| `gateway/config.py` | Add QQ env loading to `_apply_env_overrides()` |
| `gateway/run.py` | Add QQ adapter branch to `_create_adapter()` |
| `gateway/run.py` | Add QQ entries to permission maps |
| `hermes_cli/tools_config.py` | Add `"qq"` entry to `PLATFORMS` dict |
| `toolsets.py` | Add `hermes-qq` toolset + include in `hermes-gateway` |
| `~/.hermes/config.yaml` | Add `qq: [hermes-telegram]` under `platform_toolsets` *(persists across updates)* |

> The first seven patches live inside the Hermes Agent repo and are reset by `git pull`. The `config.yaml` change is in your personal config directory and persists.
