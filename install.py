#!/usr/bin/env python3
"""Install claude-usage-mcp for Claude Desktop and Claude Code on this computer.

Run from the cloned repo:  python3 install.py
It uses the repo where it is (don't move it afterwards) and:
  1. adds the MCP server to Claude Desktop's config,
  2. registers it with Claude Code (if the `claude` command is installed),
  3. sets Claude Code's status line to record plan limits, keeping any existing
     status line by chaining it.
Every config file it changes is backed up first as <name>.bak-<timestamp>.
Run with --uninstall to undo steps 1-3.
"""
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

NAME = "claude-usage"
HERE = Path(__file__).resolve().parent
SERVER = HERE / "server.py"
STATUSLINE = HERE / "statusline.py"


def desktop_config() -> Path:
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
    if system == "Windows":
        return Path(os.environ["APPDATA"]) / "Claude/claude_desktop_config.json"
    return Path.home() / ".config/Claude/claude_desktop_config.json"


def claude_settings() -> Path:
    base = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    return base / "settings.json"


def load(path: Path) -> dict:
    if not path.exists() or not path.read_text().strip():
        return {}
    return json.loads(path.read_text())


def save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup, n = path.with_name(f"{path.name}.bak-{stamp}"), 1
        while backup.exists():
            n += 1
            backup = path.with_name(f"{path.name}.bak-{stamp}-{n}")
        shutil.copy2(path, backup)
        print(f"  backed up {path.name} -> {backup.name}")
    path.write_text(json.dumps(data, indent=2) + "\n")


def find_uv() -> str:
    uv = shutil.which("uv")
    for candidate in (Path.home() / ".local/bin/uv", Path.home() / ".cargo/bin/uv", Path("/opt/homebrew/bin/uv")):
        if not uv and candidate.exists():
            uv = str(candidate)
    if not uv:
        sys.exit(
            "uv is not installed. Install it, then run this again:\n"
            "  macOS/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh\n"
            '  Windows:     powershell -c "irm https://astral.sh/uv/install.ps1 | iex"'
        )
    return str(Path(uv).resolve())


def our_statusline(existing: str | None) -> str:
    py = "python3" if platform.system() != "Windows" else "python"
    cmd = f"{py} {shlex.quote(str(STATUSLINE))}"
    if existing:
        cmd += f" --then {shlex.quote(existing)}"
    return cmd


def install() -> None:
    uv = find_uv()

    print("1. Claude Desktop")
    path = desktop_config()
    cfg = load(path)
    cfg.setdefault("mcpServers", {})[NAME] = {"command": uv, "args": ["run", str(SERVER)]}
    save(path, cfg)
    print(f"  added '{NAME}' to {path}")

    print("2. Claude Code MCP server")
    claude = shutil.which("claude")
    if claude:
        subprocess.run([claude, "mcp", "remove", "--scope", "user", NAME], capture_output=True)
        r = subprocess.run(
            [claude, "mcp", "add", "--scope", "user", NAME, "--", uv, "run", str(SERVER)],
            capture_output=True, text=True,
        )
        print("  " + (r.stdout or r.stderr).strip())
    else:
        print("  `claude` command not found; skipped (Claude Desktop is set up regardless)")

    print("3. Claude Code status line")
    path = claude_settings()
    settings = load(path)
    current = (settings.get("statusLine") or {}).get("command")
    if current and str(STATUSLINE) in current:
        print("  already set")
    else:
        settings["statusLine"] = {"type": "command", "command": our_statusline(current)}
        save(path, settings)
        print(f"  set statusLine{' (chained to your existing one)' if current else ''}")

    print(
        "\nDone. Restart Claude Desktop, then send one message in Claude Code so your plan\n"
        "limits get recorded. After that, ask Claude: \"what's my usage?\""
    )


def uninstall() -> None:
    path = desktop_config()
    cfg = load(path)
    if NAME in cfg.get("mcpServers", {}):
        del cfg["mcpServers"][NAME]
        save(path, cfg)
        print(f"removed from {path}")
    if shutil.which("claude"):
        subprocess.run(["claude", "mcp", "remove", "--scope", "user", NAME], capture_output=True)
        print("removed from Claude Code")
    path = claude_settings()
    settings = load(path)
    cmd = (settings.get("statusLine") or {}).get("command", "")
    if str(STATUSLINE) in cmd:
        parts = shlex.split(cmd)
        if "--then" in parts:
            settings["statusLine"]["command"] = parts[parts.index("--then") + 1]
        else:
            del settings["statusLine"]
        save(path, settings)
        print("restored status line")


if __name__ == "__main__":
    uninstall() if "--uninstall" in sys.argv else install()
