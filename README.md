# claude-usage

An MCP server that lets Claude see your Claude subscription usage. Ask things like
"how much of my weekly limit is left?" or "which project used the most tokens this week?"

## What it reports

| Tool | Data | Source | Covers |
|---|---|---|---|
| `get_plan_limits` | % used of the 5-hour and 7-day windows, reset times | Anthropic, via Claude Code's status line | Your whole plan: claude.ai, Desktop, Claude Code |
| `get_plan_limit_history` | How those percentages moved over the last N hours | Same, recorded over time | Same |
| `get_token_usage` | Input, output and cache tokens by day, model, project or session | `~/.claude/projects/**/*.jsonl` | Claude Code only |

The plan limits are the same numbers `/usage` and claude.ai's usage page show. Claude Code
only hands them to its status line after a response, so a snapshot can be out of date. When
you ask from inside Claude Code it is current; from Claude Desktop it's as of your last
Claude Code message, and the tool reports how old it is.

## Quick install

Needs [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`),
which installs the `mcp` package automatically. Then:

```bash
git clone https://github.com/xynexus/claude-usage.git ~/claude-usage
```

```bash
python3 ~/claude-usage/install.py
```

It adds the server to Claude Desktop and Claude Code and sets up the status line (keeping
any status line you already have). Each config file it changes is backed up first.
`python3 install.py --uninstall` undoes it. Restart Claude Desktop afterwards.

## Manual setup

The same steps by hand. Put this folder somewhere permanent, e.g. `~/claude-usage`.

### 1. Record plan limits with the status line

Add to `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 ~/claude-usage/statusline.py"
  }
}
```

That shows `[Opus] | 5h: 24% | 7d: 41%` at the bottom of Claude Code. If you already have a
status line, keep it by chaining it; it gets the same input and its output is shown instead:

```json
"command": "python3 ~/claude-usage/statusline.py --then '~/.claude/statusline.sh'"
```

Send a message in Claude Code once, and `~/.claude/usage-mcp/rate_limits.json` appears.

### 2. Register the MCP server

Claude Code, for all your projects:

```bash
claude mcp add --scope user claude-usage -- uv run ~/claude-usage/server.py
```

Claude Desktop: Settings → Developer → Edit Config, and add the server below. Use full paths;
Desktop doesn't expand `~` or see your shell's PATH. `which uv` prints the uv path.

```json
{
  "mcpServers": {
    "claude-usage": {
      "command": "/Users/YOU/.local/bin/uv",
      "args": ["run", "/Users/YOU/claude-usage/server.py"]
    }
  }
}
```

Restart Claude Desktop, then ask "what's my Claude usage?"

## Notes

- Plan limits only exist on Pro, Max and Ultra plans. API-key users get no `rate_limits`.
- If you set `CLAUDE_CONFIG_DIR`, both scripts use it instead of `~/.claude`.
- Claude Code writes each response to the log several times; `get_token_usage` dedupes by
  message and request id so nothing is counted twice.
- Cache reads usually make up most of the "total" tokens. They're re-reads of context
  already sent and are much cheaper to serve, so input + output + cache creation is a better
  measure of real work. For how close you are to your limit, use `get_plan_limits`.
- Everything stays on your machine. The server makes no network calls.
