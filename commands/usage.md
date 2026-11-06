---
description: Show your Claude plan usage limits and recent Claude Code token usage
argument-hint: "[days, default 7]"
---

Report the user's Claude usage. Call `get_plan_limits`, and `get_token_usage` with
`days` set to $ARGUMENTS (7 if empty) grouped by day, then by project.

Lead with the plan limits: percent used and time until reset for the 5-hour and weekly
windows, and how old the reading is. If the reading is missing, say to run
`/plan-usage:setup` and send a message. Then summarize token usage briefly: the total,
the busiest day and the top projects. Use input + output + cache-creation tokens as the
measure of work and mention cache reads separately, since they dominate the raw total.
Keep it short; a small table is fine.
