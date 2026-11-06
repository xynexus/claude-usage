#!/usr/bin/env python3
"""Point Claude Code's status line at the plan-limit recorder.

Plugins can't set the status line themselves, so this does it. The recorder is
copied to ~/.claude/usage-mcp/statusline.py, a path that stays put when the
plugin updates. An existing status line is kept by chaining it (--then).

    setup_statusline.py            install (backs up settings.json first)
    setup_statusline.py --refresh  update the copied recorder if installed; silent
    setup_statusline.py --remove   restore the previous status line
"""
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SOURCE = PLUGIN_ROOT / "statusline.py"
CLAUDE_DIR = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
TARGET = CLAUDE_DIR / "usage-mcp" / "statusline.py"
SETTINGS = CLAUDE_DIR / "settings.json"


def ours(cmd: str) -> bool:
    """True for a status line set by this plugin or the earlier install.py."""
    return "statusline.py" in cmd and ("usage-mcp" in cmd or "claude-usage" in cmd)


def chained(cmd: str):
    """The user's own status line that `cmd` chains to, if any."""
    try:
        parts = shlex.split(cmd)
    except ValueError:
        return None
    if "--then" in parts and parts.index("--then") + 1 < len(parts):
        return parts[parts.index("--then") + 1]
    return None


def load_settings() -> dict:
    if SETTINGS.exists() and SETTINGS.read_text().strip():
        return json.loads(SETTINGS.read_text())
    return {}


def save_settings(settings: dict) -> None:
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    if SETTINGS.exists():
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup, n = SETTINGS.with_name(f"settings.json.bak-{stamp}"), 1
        while backup.exists():
            n += 1
            backup = SETTINGS.with_name(f"settings.json.bak-{stamp}-{n}")
        shutil.copy2(SETTINGS, backup)
        print(f"Backed up settings.json to {backup}")
    SETTINGS.write_text(json.dumps(settings, indent=2) + "\n")


def copy_recorder() -> None:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE, TARGET)


def install() -> None:
    copy_recorder()
    settings = load_settings()
    current = (settings.get("statusLine") or {}).get("command")
    user_line = (chained(current) if ours(current) else current) if current else None

    py = shlex.quote(sys.executable or "python3")
    cmd = f"{py} {shlex.quote(str(TARGET))}"
    if user_line:
        cmd += f" --then {shlex.quote(user_line)}"

    if current == cmd:
        print("Status line already set up.")
    else:
        settings["statusLine"] = {"type": "command", "command": cmd}
        save_settings(settings)
        print("Status line set to record plan limits" + (f", chained to: {user_line}" if user_line else "."))

    # The pre-plugin install.py registered the same server with Claude Code at
    # user scope; with the plugin installed that would duplicate every tool.
    claude = shutil.which("claude")
    if claude:
        r = subprocess.run([claude, "mcp", "get", "claude-usage"], capture_output=True, text=True)
        if r.returncode == 0 and "server.py" in r.stdout:
            subprocess.run([claude, "mcp", "remove", "--scope", "user", "claude-usage"], capture_output=True)
            print("Removed the older stand-alone 'claude-usage' MCP server; the plugin replaces it.")

    print("Plan limits will be recorded after Claude Code's next response.")


def refresh() -> None:
    # Runs from a SessionStart hook: stdout would become context, so stay quiet.
    try:
        if TARGET.exists() and TARGET.read_bytes() != SOURCE.read_bytes():
            copy_recorder()
    except OSError:
        pass


def remove() -> None:
    settings = load_settings()
    current = (settings.get("statusLine") or {}).get("command", "")
    if not ours(current):
        print("Status line isn't set by plan-usage; nothing to change.")
        return
    user_line = chained(current)
    if user_line:
        settings["statusLine"]["command"] = user_line
    else:
        del settings["statusLine"]
    save_settings(settings)
    print("Restored your previous status line." if user_line else "Removed the status line.")


if __name__ == "__main__":
    if "--refresh" in sys.argv:
        refresh()
    elif "--remove" in sys.argv:
        remove()
    else:
        install()
