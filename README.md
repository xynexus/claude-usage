# plan-usage

A Claude plugin that lets Claude see your Claude subscription usage. Ask things like
"how much of my weekly limit is left?" or "which project used the most tokens this week?",
or run `/plan-usage:usage`.

## What it reports

| Tool | Data | Source | Covers |
|---|---|---|---|
| `get_plan_limits` | % used of the 5-hour and 7-day windows, reset times | Anthropic, via Claude Code's status line | Your whole plan: claude.ai, Desktop, Claude Code |
| `get_plan_limit_history` | How those percentages moved over the last N hours | Same, recorded over time | Same |
| `get_token_usage` | Input, output and cache tokens by day, model, project or session | `~/.claude/projects/**/*.jsonl` | Claude Code only |

The plan limits are the same numbers `/usage` and claude.ai's usage page show. Claude Code
receives them with each response and passes them to its status line, which is where this
plugin records them. So a reading is as fresh as your last Claude Code response, and the
tool always says how old it is.

## Install

Needs Python 3 (`python3`). Nothing else: the server uses only the standard library.

**Claude Desktop or claude.ai:** Customize → Plugins → Add → **Upload plugin**, and choose
`plan-usage.zip`. Or **Add marketplace** with `xynexus/claude-usage` to get updates (for a
private repo, connect GitHub when asked). The plugin then also reaches Claude Code on the
same account as a synced plugin.

**Claude Code:**

```
/plugin install plan-usage --marketplace xynexus/claude-usage
```

**Then, once, in Claude Code:** run `/plan-usage:setup`. Plugins can't set the status line
themselves, so this points it at the recorder, keeping any status line you already have,
and backs up `settings.json` first. Send one message afterwards and your plan limits are
recorded. `/plan-usage:setup remove` undoes it.

## Where it works

| | Claude Code | Cowork | Desktop / claude.ai chat |
|---|---|---|---|
| Plan limits and token tools | Yes | Yes, in Cowork sessions on your computer | No: chat doesn't run local servers from plugins |
| `/plan-usage:usage` | Yes | Yes | Loads as a skill, but has no tools to call |

For regular Desktop chat, add the server to Desktop's own config instead. From an unzipped
copy or clone you'll keep:

```bash
python3 install.py
```

Restart Claude Desktop afterwards. `python3 install.py --uninstall` removes it.

## Upgrading from the stand-alone version

If you used the earlier `install.py` that registered `claude-usage` with uv:

- `/plan-usage:setup` moves your status line over and removes the old Claude Code server, so
  the tools don't appear twice.
- Re-run `python3 install.py` from the new version to replace the old Desktop chat entry.

## Notes

- Plan limits only exist on Pro, Max and Ultra plans. API-key users get no `rate_limits`.
- If you set `CLAUDE_CONFIG_DIR`, everything uses it instead of `~/.claude`. Recorded data
  lives in `~/.claude/usage-mcp/`.
- Claude Code writes each response to its log several times; `get_token_usage` dedupes by
  message and request id so nothing is counted twice.
- Cache reads usually make up most of the "total" tokens. They're re-reads of context
  already sent and are much cheaper to serve, so input + output + cache creation is a better
  measure of real work. For how close you are to your limit, use `get_plan_limits`.
- Everything stays on your machine. The server makes no network calls.
