# 故障排查 Q&A

本文档记录在部署 QQ 插件与 Hermes Agent 集成过程中遇到的真实问题及解决方案。

---

## `git pull` 更新 Hermes Agent 后，QQ 插件突然失效

**现象：** QQ 之前正常运行，执行 `git pull` 更新 Hermes 后，Gateway 启动不显示任何 QQ 相关日志，QQ 完全不响应。

**根本原因：** QQ 插件需要对 Hermes 核心文件进行两处手动补丁，这两处修改每次 `git pull` 都会被覆盖：

1. `gateway/config.py` — 缺少 `Platform.QQ` 枚举值
2. `gateway/run.py` — 缺少 QQ 适配器加载分支

**解决方案：** 每次 `git pull` 后重新应用以下补丁。

**`gateway/config.py`** — 在 `Platform` 枚举类中添加（例如放在 `BLUEBUBBLES` 之后）：

```python
QQ = "qq"
```

**`gateway/run.py`** — 在 `_create_adapter()` 方法的 BlueBubbles 适配器块之后添加：

```python
elif platform == Platform.QQ:
    from gateway.platforms.qq import QQAdapter, check_qq_requirements
    if not check_qq_requirements():
        logger.warning("QQ: qq-botpy not installed")
        return None
    return QQAdapter(config)
```

---

## `ModuleNotFoundError: No module named 'botpy'`

**现象：** 直接在终端执行 `hermes gateway run` 时崩溃，报错：

```
ModuleNotFoundError: No module named 'botpy'
```

**根本原因：** `hermes` CLI 可执行文件使用**系统 Python**（`/usr/bin/python3`），而 `qq-botpy` 安装在 **Hermes venv**（`~/.hermes/hermes-agent/venv`）中。直接运行 CLI 会绕过 venv。

**解决方案：** 始终通过 systemd 启动 Gateway，而非直接执行：

```bash
hermes gateway start     # 正确 —— 使用 venv Python
hermes gateway restart   # 正确 —— 使用 venv Python

# 不要直接用：
hermes gateway run       # 使用系统 Python，找不到 venv 中的包
```

如果确实需要前台运行调试，请先激活 venv：

```bash
~/.hermes/hermes-agent/venv/bin/python -m hermes_cli.main gateway run
```

---

## 发消息时报 `KeyError: 'qq'`

**现象：** 机器人收到消息，但回复：

```
Sorry, I encountered an error (KeyError).
'qq'
```

**根本原因：** Hermes 核心代码中有两处缺失注册：

1. `hermes_cli/tools_config.py` — `PLATFORMS` 字典中没有 `qq` 条目
2. `~/.hermes/config.yaml` — `platform_toolsets` 部分没有 `qq` 条目

**修复 1 — `hermes_cli/tools_config.py`：** 在 `PLATFORMS` 字典中添加：

```python
"qq": {"label": "🐧 QQ", "default_toolset": "hermes-qq"},
```

**修复 2 — `~/.hermes/config.yaml`：** 在 `platform_toolsets:` 下添加：

```yaml
platform_toolsets:
  # ... 现有条目 ...
  qq:
  - hermes-telegram
```

然后重启 Gateway：

```bash
hermes gateway restart
```

---

## 机器人提示「No home channel is set for Qq」

**现象：** 发出第一条消息后，机器人回复：

```
📬 No home channel is set for Qq. A home channel is where Hermes delivers cron job results and cross-platform messages.
Type /sethome to make this chat your home channel, or ignore to skip.
```

**这不是错误。** 这是一次性提示，询问你是否将当前 QQ 聊天设为定时任务结果和跨平台消息的推送目标。

- 输入 `/sethome` 将此聊天设为 Home Channel。
- 如果不使用定时任务或跨平台功能，直接忽略即可。

---

## 机器人回复「Hi~ I don't recognize you yet!」—— 配对流程

**现象：** 当 `QQ_ALLOW_ALL_USERS=false` 时，新用户收到配对码提示：

```
Hi~ I don't recognize you yet!
Here's your pairing code: XXXXXXXX
Ask the bot owner to run:
hermes pairing approve qq XXXXXXXX
```

**解决方案：** 在服务器上执行批准命令：

```bash
hermes pairing approve qq <配对码>
```

用户下次发消息时将被自动识别。这是 `QQ_ALLOW_ALL_USERS=false` 时的正常访问控制流程。

---

## 每次更新后需要重新应用的补丁汇总

| 文件 | 修改内容 |
|------|---------|
| `gateway/config.py` | 在 `Platform` 枚举中添加 `QQ = "qq"` |
| `gateway/run.py` | 在 `_create_adapter()` 中添加 QQ 适配器分支 |
| `hermes_cli/tools_config.py` | 在 `PLATFORMS` 字典中添加 `"qq"` 条目 |
| `~/.hermes/config.yaml` | 在 `platform_toolsets` 下添加 `qq: [hermes-telegram]` |

> **说明：** 前三处文件补丁位于 Hermes Agent 仓库内部，会被 `git pull` 重置。`config.yaml` 修改位于个人配置目录，更新后保持不变。
