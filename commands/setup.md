---
description: Set up Claude Code's status line to record your plan usage limits
argument-hint: "[remove]"
allowed-tools: Bash(python3:*)
---

If the arguments are "remove" (arguments: "$ARGUMENTS"), run this instead, show its output,
and stop:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/setup_statusline.py" --remove
```

Otherwise run this command and show the user its output:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/setup_statusline.py"
```

Then explain in a sentence or two: Claude Code now records the 5-hour and weekly plan
usage percentages after each response, the status line shows them, and the
`get_plan_limits` tool reads them. Usage on claude.ai and Claude Desktop counts toward the
same limits, but the numbers refresh only when Claude Code gets a response. If the output
mentions a backup, say where it is. To undo it later: `/plan-usage:setup remove`.

If `python3` isn't found, tell the user the plugin needs Python 3 installed.
