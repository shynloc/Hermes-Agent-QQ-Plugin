#!/usr/bin/env bash
# Hermes Agent QQ Plugin Installer
# Applies all required Hermes core patches and installs dependencies.
# Safe to run multiple times (idempotent).

set -e

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
HERMES_AGENT="$HERMES_HOME/hermes-agent"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Colors ────────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC}  $1"; }
fail() { echo -e "${RED}✗${NC} $1"; exit 1; }

echo ""
echo "Hermes Agent QQ Plugin Installer"
echo "================================="
echo ""

# ── Check Hermes is installed ─────────────────────────────────────────────────
[ -d "$HERMES_AGENT" ] || fail "Hermes Agent not found at $HERMES_AGENT\n  Set HERMES_HOME env var if installed elsewhere."

PYTHON="$HERMES_AGENT/venv/bin/python3"
[ -f "$PYTHON" ] || fail "Hermes venv Python not found at $PYTHON"

CONFIG_PY="$HERMES_AGENT/gateway/config.py"
RUN_PY="$HERMES_AGENT/gateway/run.py"
TOOLS_CONFIG="$HERMES_AGENT/hermes_cli/tools_config.py"
PLATFORMS_PY="$HERMES_AGENT/hermes_cli/platforms.py"
TOOLSETS="$HERMES_AGENT/toolsets.py"
PLATFORMS_DIR="$HERMES_AGENT/gateway/platforms"

for f in "$CONFIG_PY" "$RUN_PY" "$TOOLS_CONFIG" "$TOOLSETS"; do
    [ -f "$f" ] || fail "Required file not found: $f"
done

# ── Step 1: Copy qq.py ────────────────────────────────────────────────────────
echo "Step 1/6  Copy qq.py to gateway/platforms/"
if [ -f "$SCRIPT_DIR/qq.py" ]; then
    cp "$SCRIPT_DIR/qq.py" "$PLATFORMS_DIR/qq.py"
    ok "qq.py installed to $PLATFORMS_DIR/qq.py"
else
    fail "qq.py not found in $SCRIPT_DIR — run this script from the plugin directory."
fi

# ── Step 2: Install Python dependencies ──────────────────────────────────────
echo ""
echo "Step 2/6  Install Python dependencies (qq-botpy, pysilk)"
UV="$(command -v uv 2>/dev/null || true)"
if [ -n "$UV" ]; then
    "$UV" pip install qq-botpy pysilk --python "$PYTHON" --quiet
    ok "qq-botpy and pysilk installed via uv"
else
    "$PYTHON" -m pip install qq-botpy pysilk --quiet
    ok "qq-botpy and pysilk installed via pip"
fi

# ── Python patcher ────────────────────────────────────────────────────────────
# All multi-line text patches are done via Python for reliability.
patch_file() {
    local file="$1"
    local description="$2"
    local old="$3"
    local new="$4"
    local marker="${5:-}"   # optional: explicit string to check for "already applied"

    "$PYTHON" - "$file" "$description" "$old" "$new" "$marker" <<'PYEOF'
import sys

file_path, description, old, new = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
marker = sys.argv[5] if len(sys.argv) > 5 else ""
content = open(file_path).read()

already = (marker and marker in content) or (not marker and new in content)
if already:
    print(f"  [already applied] {description}")
elif old in content:
    open(file_path, 'w').write(content.replace(old, new, 1))
    print(f"  [patched] {description}")
else:
    print(f"  [WARN] anchor not found — skipping: {description}")
PYEOF
}

# ── Step 3: Patch gateway/config.py ──────────────────────────────────────────
echo ""
echo "Step 3/6  Patch gateway/config.py"

# 3a: Add QQ to Platform enum
patch_file "$CONFIG_PY" "Platform enum: add QQ = 'qq'" \
    '    BLUEBUBBLES = "bluebubbles"' \
    '    BLUEBUBBLES = "bluebubbles"
    QQ = "qq"'

# 3b: Add QQ to get_connected_platforms()
patch_file "$CONFIG_PY" "get_connected_platforms: QQ check" \
    '            elif platform == Platform.BLUEBUBBLES and config.extra.get("server_url") and config.extra.get("password"):
                connected.append(platform)' \
    '            elif platform == Platform.BLUEBUBBLES and config.extra.get("server_url") and config.extra.get("password"):
                connected.append(platform)
            # QQ uses app_id and app_secret from environment variables
            elif platform == Platform.QQ and os.getenv("QQ_APP_ID") and os.getenv("QQ_APP_SECRET"):
                connected.append(platform)'

# 3c: Add QQ env loading to _apply_env_overrides()
patch_file "$CONFIG_PY" "_apply_env_overrides: QQ env loading" \
    '    # Session settings' \
    '    # QQ
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

    # Session settings'

ok "gateway/config.py patched"

# ── Step 4: Patch gateway/run.py ─────────────────────────────────────────────
echo ""
echo "Step 4/6  Patch gateway/run.py"

# 4a: QQ adapter in _create_adapter()
patch_file "$RUN_PY" "_create_adapter: QQ adapter branch" \
    '            return BlueBubblesAdapter(config)

        return None' \
    '            return BlueBubblesAdapter(config)

        elif platform == Platform.QQ:
            from gateway.platforms.qq import QQAdapter, check_qq_requirements
            if not check_qq_requirements():
                logger.warning("QQ: qq-botpy not installed, run: uv pip install qq-botpy")
                return None
            return QQAdapter(config)

        return None' \
    'elif platform == Platform.QQ:'

# 4b: Permission map entries
patch_file "$RUN_PY" "platform_env_map: QQ entry" \
    '            Platform.BLUEBUBBLES: "BLUEBUBBLES_ALLOWED_USERS",' \
    '            Platform.BLUEBUBBLES: "BLUEBUBBLES_ALLOWED_USERS",
            Platform.QQ: "QQ_ALLOWED_USERS",'

patch_file "$RUN_PY" "platform_allow_all_map: QQ entry" \
    '            Platform.BLUEBUBBLES: "BLUEBUBBLES_ALLOW_ALL_USERS",' \
    '            Platform.BLUEBUBBLES: "BLUEBUBBLES_ALLOW_ALL_USERS",
            Platform.QQ: "QQ_ALLOW_ALL_USERS",'

ok "gateway/run.py patched"

# ── Step 5: Patch PLATFORMS registry (location changed across Hermes versions) ─
echo ""
echo "Step 5/6  Patch PLATFORMS registry"

# Hermes moved PLATFORMS from tools_config.py (old) to hermes_cli/platforms.py (new).
# Try the new location first; fall back to the old one.
if [ -f "$PLATFORMS_PY" ]; then
    patch_file "$PLATFORMS_PY" "platforms.py: qq entry" \
        '    ("weixin",         PlatformInfo(label="💬 Weixin",          default_toolset="hermes-weixin")),' \
        '    ("weixin",         PlatformInfo(label="💬 Weixin",          default_toolset="hermes-weixin")),
    ("qq",             PlatformInfo(label="🐧 QQ",               default_toolset="hermes-qq")),' \
        '"hermes-qq"'
    ok "hermes_cli/platforms.py patched"
else
    patch_file "$TOOLS_CONFIG" "PLATFORMS dict: qq entry" \
        '    "weixin": {"label": "💬 Weixin", "default_toolset": "hermes-weixin"},' \
        '    "weixin": {"label": "💬 Weixin", "default_toolset": "hermes-weixin"},
    "qq": {"label": "🐧 QQ", "default_toolset": "hermes-qq"},' \
        '"hermes-qq"'
    ok "hermes_cli/tools_config.py patched (legacy location)"
fi

# ── Step 6: Patch toolsets.py ─────────────────────────────────────────────────
echo ""
echo "Step 6/6  Patch toolsets.py"

patch_file "$TOOLSETS" "toolsets: hermes-qq definition" \
    '    "hermes-webhook": {' \
    '    "hermes-qq": {
        "description": "QQ platform toolset",
        "tools": [],
        "includes": ["hermes-core"]
    },

    "hermes-webhook": {'

patch_file "$TOOLSETS" "hermes-gateway includes: add hermes-qq" \
    '"hermes-weixin", "hermes-webhook"' \
    '"hermes-weixin", "hermes-qq", "hermes-webhook"'

ok "toolsets.py patched"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "All patches applied successfully!"
echo ""
echo "Next steps:"
echo "  1. Add credentials to ~/.hermes/.env:"
echo "       QQ_APP_ID=your_app_id"
echo "       QQ_APP_SECRET=your_app_secret"
echo "       QQ_ALLOW_ALL_USERS=false"
echo ""
echo "  2. Enable the platform in ~/.hermes/config.yaml:"
echo "       platforms:"
echo "         qq:"
echo "           enabled: true"
echo ""
echo "  3. Add qq to platform_toolsets in ~/.hermes/config.yaml:"
echo "       platform_toolsets:"
echo "         qq:"
echo "         - hermes-telegram"
echo ""
echo "  4. Restart the gateway:"
echo "       hermes gateway restart"
echo ""
