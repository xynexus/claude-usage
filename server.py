# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=2.3,<3"]
# ///
"""MCP server that lets Claude read your Claude subscription usage.

Two data sources, both on your own machine:

1. Plan limits (accurate): the 5-hour and 7-day usage percentages Claude Code
   receives from Anthropic, recorded by statusline.py. These are the same
   numbers `/usage` and claude.ai's usage page show, and they count all your
   usage on the plan (claude.ai chat, Desktop and Claude Code).
2. Token counts: per-response token usage from Claude Code's session logs
   (~/.claude/projects/**/*.jsonl). Claude Code only; chat on claude.ai is not
   logged locally.
"""
from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("claude-usage")

WINDOWS = {"five_hour": "5-hour session window", "seven_day": "7-day weekly window"}


def claude_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def data_dir() -> Path:
    return claude_dir() / "usage-mcp"


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts).astimezone().isoformat(timespec="minutes")


def ago(seconds: float) -> str:
    seconds = abs(seconds)
    if seconds < 90:
        return f"{seconds:.0f}s"
    if seconds < 5400:
        return f"{seconds / 60:.0f}m"
    if seconds < 172800:
        return f"{seconds / 3600:.1f}h"
    return f"{seconds / 86400:.1f}d"


# --------------------------------------------------------------------------- plan limits


@mcp.tool()
def get_plan_limits() -> dict:
    """Current Claude subscription (Pro/Max) usage limits: percent used of the
    rolling 5-hour window and the 7-day weekly window, and when each resets.

    These are Anthropic's own numbers (the same as /usage and the claude.ai
    usage page) and include usage from claude.ai chat and Claude Desktop, but
    they are captured only when Claude Code receives a response, so check
    `snapshot_age` for how fresh they are.
    """
    path = data_dir() / "rate_limits.json"
    if not path.exists():
        return {
            "error": "No usage snapshot yet.",
            "fix": "Set Claude Code's statusLine to run statusline.py (see README), "
            "then send one message in Claude Code. Only Pro/Max/Ultra plans "
            "report plan limits.",
        }
    snap = json.loads(path.read_text())
    now = time.time()
    captured = snap["captured_at"]
    out: dict = {
        "snapshot_taken": iso(captured),
        "snapshot_age": ago(now - captured),
        "windows": {},
    }
    for key, limit in snap["rate_limits"].items():
        if not isinstance(limit, dict):
            continue
        w: dict = {"name": WINDOWS.get(key, key)}
        pct = limit.get("used_percentage")
        resets = limit.get("resets_at")
        if resets and resets <= now:
            w["status"] = (
                f"Reset at {iso(resets)} after the snapshot; current usage is unknown "
                "(near 0% unless you've used Claude since). It updates on the next "
                "Claude Code response."
            )
            w["used_percentage_before_reset"] = pct
        else:
            w["used_percentage"] = pct
            if pct is not None:
                w["remaining_percentage"] = round(max(0.0, 100 - pct), 1)
            if resets:
                w["resets_at"] = iso(resets)
                w["resets_in"] = ago(resets - now)
        for extra in ("used_usd", "limit_usd", "period"):  # gateway spend limits
            if extra in limit:
                w[extra] = limit[extra]
        out["windows"][key] = w
    if now - captured > 15 * 60:
        out["note"] = (
            "Snapshot is older than 15 minutes; usage on claude.ai or Desktop since "
            "then isn't reflected."
        )
    return out


@mcp.tool()
def get_plan_limit_history(hours: float = 24) -> dict:
    """How plan-limit usage percentages changed over the last `hours` hours,
    for spotting burn rate (e.g. "5h window went 10% -> 60% in the last hour").
    Points are recorded only when Claude Code was in use."""
    hist = data_dir() / "history.jsonl"
    if not hist.exists():
        return {"error": "No history yet; see get_plan_limits for setup."}
    cutoff = time.time() - hours * 3600
    points = []
    for line in hist.read_text().splitlines():
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec["t"] < cutoff:
            continue
        p = {"time": iso(rec["t"])}
        for key in WINDOWS:
            pct = (rec["rate_limits"].get(key) or {}).get("used_percentage")
            if pct is not None:
                p[key] = pct
        points.append(p)
    # Keep the answer compact: at most ~60 evenly spaced points plus the last.
    if len(points) > 60:
        step = len(points) / 60
        points = [points[int(i * step)] for i in range(60)] + [points[-1]]
    return {"hours": hours, "points": points}


# --------------------------------------------------------------------------- token counts


def iter_responses(since: float):
    """Yield one record per API response in Claude Code's logs, newest copy
    wins. Claude Code writes a line per content block, each repeating the
    response's usage, so records are deduplicated by message id + request id."""
    root = claude_dir() / "projects"
    if not root.exists():
        return
    seen: dict[tuple, dict] = {}
    for f in root.rglob("*.jsonl"):
        try:
            if f.stat().st_mtime < since:
                continue
            fh = f.open(encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                if '"usage"' not in line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                msg = d.get("message")
                if d.get("type") != "assistant" or not isinstance(msg, dict):
                    continue
                usage = msg.get("usage")
                ts = d.get("timestamp")
                if not usage or not ts:
                    continue
                try:
                    t = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
                except ValueError:
                    continue
                if t < since:
                    continue
                key = (msg.get("id"), d.get("requestId")) if msg.get("id") else (f, line)
                seen[key] = {
                    "t": t,
                    "model": msg.get("model") or "unknown",
                    "project": d.get("cwd") or f.parent.name,
                    "session": d.get("sessionId") or f.stem,
                    "usage": usage,
                }
    yield from seen.values()


def empty_totals() -> dict:
    return {
        "responses": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
        "total_tokens": 0,
    }


def add(tot: dict, u: dict) -> None:
    i = u.get("input_tokens") or 0
    o = u.get("output_tokens") or 0
    cw = u.get("cache_creation_input_tokens") or 0
    cr = u.get("cache_read_input_tokens") or 0
    tot["responses"] += 1
    tot["input_tokens"] += i
    tot["output_tokens"] += o
    tot["cache_creation_tokens"] += cw
    tot["cache_read_tokens"] += cr
    tot["total_tokens"] += i + o + cw + cr


@mcp.tool()
def get_token_usage(
    days: float = 7,
    group_by: Literal["day", "model", "project", "session"] = "day",
    project: str | None = None,
    limit: int = 30,
) -> dict:
    """Token usage from Claude Code's local session logs over the last `days`
    days, grouped by day, model, project directory or session.

    Covers Claude Code only (not claude.ai chat). `project` filters to project
    paths containing that text. Cache reads are cheap and usually dominate the
    total; input + output + cache_creation is a better measure of real work.
    For plan limit percentages use get_plan_limits instead.
    """
    since = time.time() - days * 86400
    groups: dict[str, dict] = defaultdict(empty_totals)
    last_seen: dict[str, float] = {}
    overall = empty_totals()
    for r in iter_responses(since):
        if project and project.lower() not in r["project"].lower():
            continue
        if group_by == "day":
            k = datetime.fromtimestamp(r["t"]).strftime("%Y-%m-%d")
        else:
            k = r[group_by]
        add(groups[k], r["usage"])
        add(overall, r["usage"])
        last_seen[k] = max(last_seen.get(k, 0), r["t"])

    if group_by == "day":
        order = sorted(groups, reverse=True)
    elif group_by == "session":
        order = sorted(groups, key=lambda k: last_seen[k], reverse=True)
    else:
        order = sorted(groups, key=lambda k: groups[k]["total_tokens"], reverse=True)

    rows = []
    for k in order[:limit]:
        row = {group_by: k, **groups[k]}
        if group_by in ("session", "project"):
            row["last_active"] = iso(last_seen[k])
        rows.append(row)
    return {
        "since": (datetime.now() - timedelta(days=days)).astimezone().isoformat(timespec="minutes"),
        "group_by": group_by,
        "totals": overall,
        "groups": rows,
        "groups_omitted": max(0, len(order) - limit),
    }


if __name__ == "__main__":
    mcp.run()
