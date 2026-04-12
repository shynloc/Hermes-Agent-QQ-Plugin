# 故障排查 Q&A

本文档记录在多台机器上部署 QQ 插件与 Hermes Agent 集成过程中遇到的真实问题及解决方案。

## 为什么会有这么多地方要改？

Hermes 没有插件自动发现机制。新增一个平台需要手动修改 **4–5 个核心文件**。本插件只提供了适配器代码（`qq.py`），框架注册补丁需要手动应用。下面所有报错都是漏打补丁的症状，而非 Hermes 本身的 bug，也不是用户配置错误。

---

## Gateway 启动提示「No messaging platforms enabled」

**现象：** 安装插件并重启 Gateway 后，启动日志显示：

```
No messaging platforms enabled
```

QQ 始终不连接，机器人无响应。

**根本原因：** `gateway/config.py` 中有两处方法缺少 QQ 支持：

1. `get_connected_platforms()` — 没有 QQ 条目，导致 QQ 永远不被识别为已连接平台
2. `_apply_env_overrides()` — QQ 环境变量（`QQ_APP_ID`、`QQ_APP_SECRET`）从未从 `.env` 加载到运行时配置

**修复 — `gateway/config.py`，在 `get_connected_platforms()` 里：** 在 BlueBubbles 判断后添加：

```python
elif platform == Platform.QQ and os.getenv("QQ_APP_ID") and os.getenv("QQ_APP_SECRET"):
    connected.append(platform)
```

**修复 — `gateway/config.py`，在 `_apply_env_overrides()` 里：** 添加 QQ 环境变量加载逻辑：

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

## `git pull` 更新 Hermes Agent 后，QQ 插件突然失效

**现象：** QQ 之前正常运行，执行 `git pull` 后，Gateway 启动不显示任何 QQ 相关日志，QQ 完全不响应。

**根本原因：** `Platform.QQ` 枚举值和 `run.py` 中的 QQ 适配器加载分支每次 `git pull` 都会被覆盖。

**修复 — `gateway/config.py`：** 在 `Platform` 枚举类中添加（例如放在 `BLUEBUBBLES` 之后）：

```python
QQ = "qq"
```

**修复 — `gateway/run.py`：** 在 `_create_adapter()` 方法的 BlueBubbles 适配器块之后添加：

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

**根本原因：** `hermes` CLI 使用**系统 Python**（`/usr/bin/python3`），而 `qq-botpy` 安装在 **Hermes venv** 中。直接运行 CLI 会绕过 venv。

**解决方案：** 始终通过 systemd 启动 Gateway：

```bash
hermes gateway start     # 正确 —— 使用 venv Python
hermes gateway restart   # 正确 —— 使用 venv Python
```

如果需要前台调试，请先激活 venv：

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

**根本原因：** 三处缺失注册：

1. `hermes_cli/tools_config.py` — `PLATFORMS` 字典没有 `qq` 条目
2. `toolsets.py` — 没有定义 `hermes-qq` 工具集
3. `~/.hermes/config.yaml` — `platform_toolsets` 部分没有 `qq` 条目

**修复 1 — `hermes_cli/tools_config.py`：** 在 `PLATFORMS` 字典中（`weixin` 条目之后）添加：

```python
"qq": {"label": "🐧 QQ", "default_toolset": "hermes-qq"},
```

**修复 2 — `toolsets.py`：** 添加 `hermes-qq` 工具集定义：

```python
"hermes-qq": {
    "description": "QQ platform toolset",
    "tools": [],
    "includes": ["hermes-core"]
},
```

同时将 `"hermes-qq"` 加入 `hermes-gateway` 工具集的 `includes` 列表。

**修复 3 — `~/.hermes/config.yaml`：** 在 `platform_toolsets:` 下添加：

```yaml
platform_toolsets:
  qq:
  - hermes-telegram
```

然后重启 Gateway：

```bash
hermes gateway restart
```

---

## 权限映射缺失 —— 授权用户仍被拒绝

**现象：** 已通过配对审批的用户消息被拒绝，或用户权限校验不正常。

**根本原因：** `gateway/run.py` 中的权限查找映射表缺少 QQ 条目。

**修复 — `gateway/run.py`：** 在 `platform_env_map` 字典中添加：

```python
Platform.QQ: "QQ_ALLOWED_USERS",
```

在 `platform_allow_all_map` 字典中添加：

```python
Platform.QQ: "QQ_ALLOW_ALL_USERS",
```

---

## 机器人回复「Hi~ I don't recognize you yet!」—— 配对流程

**现象：** 当 `QQ_ALLOW_ALL_USERS=false` 时，新用户收到配对码提示：

```
Hi~ I don't recognize you yet!
Here's your pairing code: XXXXXXXX
Ask the bot owner to run:
hermes pairing approve qq XXXXXXXX
```

**解决方案：** 在服务器上执行：

```bash
hermes pairing approve qq <配对码>
```

用户下次发消息时将被自动识别。这是正常的访问控制流程。

---

## 机器人提示「No home channel is set for Qq」

**现象：** 发出第一条消息后，机器人回复：

```
📬 No home channel is set for Qq.
Type /sethome to make this chat your home channel, or ignore to skip.
```

**这不是错误。** 输入 `/sethome` 将此聊天设为 Home Channel，或直接忽略。

---

## `~/.hermes/.env` 中的环境变量未生效

**现象：** `QQ_APP_ID` 已写入 `.env`，但手动运行 Gateway 时不生效。

**根本原因：** Hermes **不会自动** source `~/.hermes/.env`。该文件仅通过 systemd 服务单元的 `EnvironmentFile=` 指令加载。

**解决方案：** 始终通过 systemd 启动（`hermes gateway start`），或手动 source 后再运行：

```bash
set -a && source ~/.hermes/.env && set +a
hermes gateway run
```

---

## 完整补丁清单（每次 `git pull` 后需重新应用）

| 文件 | 修改内容 |
|------|---------|
| `gateway/config.py` | 在 `Platform` 枚举中添加 `QQ = "qq"` |
| `gateway/config.py` | 在 `get_connected_platforms()` 中添加 QQ 校验 |
| `gateway/config.py` | 在 `_apply_env_overrides()` 中添加 QQ env 加载 |
| `gateway/run.py` | 在 `_create_adapter()` 中添加 QQ 适配器分支 |
| `gateway/run.py` | 在权限映射表中添加 QQ 条目 |
| `hermes_cli/tools_config.py` | 在 `PLATFORMS` 字典中添加 `"qq"` 条目 |
| `toolsets.py` | 添加 `hermes-qq` 工具集并加入 `hermes-gateway` includes |
| `~/.hermes/config.yaml` | 在 `platform_toolsets` 下添加 `qq` *(个人配置目录，不受 git pull 影响)* |

> 前七处补丁位于 Hermes Agent 仓库内部，会被 `git pull` 重置。`config.yaml` 位于个人配置目录，更新后保持不变。
