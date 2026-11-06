#!/usr/bin/env python3
"""Add the plan-usage MCP server to regular Claude Desktop chat.

The plugin covers Claude Code and Cowork, but Desktop chat doesn't load local
MCP servers from plugins, so chat needs an entry in claude_desktop_config.json.
Run from a folder you'll keep (the config points at server.py here):

    python3 install.py              add it (backs up the config first)
    python3 install.py --uninstall  remove it

Restart Claude Desktop afterwards.
"""
import json
import os
import platform
import shutil
import sys
import time
from pathlib import Path

NAME = "plan-usage"
LEGACY = "claude-usage"  # name used by the earlier install.py
SERVER = Path(__file__).resolve().parent / "server.py"


def desktop_config() -> Path:
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
    if system == "Windows":
        return Path(os.environ["APPDATA"]) / "Claude/claude_desktop_config.json"
    return Path.home() / ".config/Claude/claude_desktop_config.json"


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
        print(f"Backed up {path.name} to {backup.name}")
    path.write_text(json.dumps(data, indent=2) + "\n")


def main() -> None:
    path = desktop_config()
    cfg = load(path)
    servers = cfg.setdefault("mcpServers", {})
    if "--uninstall" in sys.argv:
        removed = [n for n in (NAME, LEGACY) if servers.pop(n, None) is not None]
        if not removed:
            print("plan-usage isn't in the Claude Desktop config.")
            return
        save(path, cfg)
        print(f"Removed {', '.join(removed)} from {path}")
    else:
        # Desktop doesn't see your shell's PATH, so use this Python's full path.
        servers[NAME] = {"command": sys.executable, "args": [str(SERVER)]}
        if servers.pop(LEGACY, None) is not None:
            print(f"Replaced the older '{LEGACY}' entry")
        save(path, cfg)
        print(f"Added plan-usage to {path}")
    print("Restart Claude Desktop to apply.")


if __name__ == "__main__":
    main()
