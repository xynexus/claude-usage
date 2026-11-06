#!/usr/bin/env python3
"""Claude Code status line command that records your plan usage limits.

Claude Code pipes a JSON blob to the status line command after each response.
For claude.ai Pro / Max / Ultra subscribers that blob contains `rate_limits`
(the same numbers `/usage` shows). This script saves them to disk so the
usage MCP server can report them, then prints a status line.

Usage in ~/.claude/settings.json:
    "statusLine": {"type": "command", "command": "python3 /path/to/statusline.py"}

To keep an existing status line, pass it with --then; it receives the same
stdin and its output is printed instead of the default line:
    "command": "python3 /path/to/statusline.py --then '~/.claude/my-statusline.sh'"

Standard library only, so it runs on any python3.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HISTORY_MAX_LINES = 20000  # ~ several weeks of changes; trimmed when exceeded


def data_dir() -> Path:
    base = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    return base / "usage-mcp"


def atomic_write(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.replace(tmp, path)


def record(payload: dict) -> None:
    limits = payload.get("rate_limits")
    if not isinstance(limits, dict) or not limits:
        return
    d = data_dir()
    d.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "captured_at": time.time(),
        "rate_limits": limits,
        "session_id": payload.get("session_id"),
        "model": (payload.get("model") or {}).get("id"),
        "claude_code_version": payload.get("version"),
    }
    latest = d / "rate_limits.json"
    previous = None
    try:
        previous = json.loads(latest.read_text()).get("rate_limits")
    except Exception:
        pass
    atomic_write(latest, json.dumps(snapshot, indent=2))

    # Append to history only when the numbers move, to keep the file small.
    if previous != limits:
        hist = d / "history.jsonl"
        with hist.open("a") as f:
            f.write(json.dumps({"t": snapshot["captured_at"], "rate_limits": limits}) + "\n")
        try:
            if hist.stat().st_size > HISTORY_MAX_LINES * 200:
                lines = hist.read_text().splitlines()[-HISTORY_MAX_LINES // 2 :]
                atomic_write(hist, "\n".join(lines) + "\n")
        except Exception:
            pass


def default_line(payload: dict) -> str:
    model = (payload.get("model") or {}).get("display_name") or "Claude"
    parts = [f"[{model}]"]
    limits = payload.get("rate_limits") or {}
    for key, label in (("five_hour", "5h"), ("seven_day", "7d")):
        pct = (limits.get(key) or {}).get("used_percentage")
        if pct is not None:
            parts.append(f"{label}: {pct:.0f}%")
    return " | ".join(parts)


def main() -> None:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except Exception:
        payload = {}
    try:
        record(payload)
    except Exception as e:  # never break the status line over a write error
        print(f"usage-mcp: {e}", file=sys.stderr)

    if len(sys.argv) >= 3 and sys.argv[1] == "--then":
        out = subprocess.run(sys.argv[2], shell=True, input=raw, capture_output=True, text=True)
        sys.stdout.write(out.stdout)
    else:
        print(default_line(payload))


if __name__ == "__main__":
    main()
