# Troubleshooting & Q&A

This document covers common integration issues encountered when deploying the QQ plugin with Hermes Agent. All entries are based on real debugging sessions.

---

## After `git pull` on Hermes Agent, the QQ plugin stops working

**Symptom:** QQ was working before, but after updating Hermes (`git pull`), the gateway starts with no QQ connection and no QQ-related log entries.

**Root cause:** The QQ plugin requires two manual patches to Hermes core files. These patches are wiped by every `git pull`:

1. `gateway/config.py` — `Platform.QQ` enum value is missing
2. `gateway/run.py` — QQ adapter loading branch is missing

**Fix:** Re-apply both patches after every `git pull`.

**`gateway/config.py`** — add inside the `Platform` enum (e.g. after `BLUEBUBBLES`):

```python
QQ = "qq"
```

**`gateway/run.py`** — add after the BlueBubbles adapter block inside `_create_adapter()`:

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

**Symptom:** Running `hermes gateway run` directly in the terminal crashes with:

```
ModuleNotFoundError: No module named 'botpy'
```

**Root cause:** The `hermes` CLI binary uses the **system Python** (`/usr/bin/python3`), but `qq-botpy` is installed in the **Hermes venv** (`~/.hermes/hermes-agent/venv`). Running the CLI directly bypasses the venv.

**Fix:** Always start the gateway through systemd, not directly:

```bash
hermes gateway start     # correct — uses venv Python
hermes gateway restart   # correct — uses venv Python

# Do NOT use:
hermes gateway run       # uses system Python, misses venv packages
```

If you need to test in the foreground, activate the venv first:

```bash
~/.hermes/hermes-agent/venv/bin/python -m hermes_cli.main gateway run
```

---

## `KeyError: 'qq'` when sending a message to the bot

**Symptom:** The bot receives a message but replies with:

```
Sorry, I encountered an error (KeyError).
'qq'
```

**Root cause:** Two missing registrations in Hermes core:

1. `hermes_cli/tools_config.py` — `PLATFORMS` dict has no `qq` entry
2. `~/.hermes/config.yaml` — `platform_toolsets` section has no `qq` entry

**Fix 1 — `hermes_cli/tools_config.py`:** Add inside the `PLATFORMS` dict:

```python
"qq": {"label": "🐧 QQ", "default_toolset": "hermes-qq"},
```

**Fix 2 — `~/.hermes/config.yaml`:** Add under `platform_toolsets:`:

```yaml
platform_toolsets:
  # ... existing entries ...
  qq:
  - hermes-telegram
```

Then restart the gateway:

```bash
hermes gateway restart
```

---

## Bot responds with "No home channel is set for Qq"

**Symptom:** After the first message, the bot says:

```
📬 No home channel is set for Qq. A home channel is where Hermes delivers cron job results and cross-platform messages.
Type /sethome to make this chat your home channel, or ignore to skip.
```

**This is not an error.** It is a one-time prompt asking you to designate this QQ chat as the delivery target for scheduled tasks and cross-platform notifications.

- Type `/sethome` to confirm this chat as the home channel.
- Ignore the message if you do not use cron jobs or cross-platform features.

---

## Bot says "Hi~ I don't recognize you yet!" — Pairing flow

**Symptom:** When `QQ_ALLOW_ALL_USERS=false`, new users receive a pairing code:

```
Hi~ I don't recognize you yet!
Here's your pairing code: XXXXXXXX
Ask the bot owner to run:
hermes pairing approve qq XXXXXXXX
```

**Fix:** Run the approval command on the server:

```bash
hermes pairing approve qq <CODE>
```

The user will be recognized automatically on their next message. This is the expected access-control flow when `QQ_ALLOW_ALL_USERS` is `false`.

---

## Summary of required manual patches after `git pull`

| File | Change |
|------|--------|
| `gateway/config.py` | Add `QQ = "qq"` to `Platform` enum |
| `gateway/run.py` | Add QQ adapter branch to `_create_adapter()` |
| `hermes_cli/tools_config.py` | Add `"qq"` entry to `PLATFORMS` dict |
| `~/.hermes/config.yaml` | Add `qq: [hermes-telegram]` under `platform_toolsets` |

> **Note:** The first three file patches live inside the Hermes Agent repo and are reset by `git pull`. The `config.yaml` change is in your personal config directory and persists across updates.
