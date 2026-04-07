---
name: auto-skill-loader
description: >
  Auto-load approved skills into agent sessions at startup. Use when: the agent starts
  a new session and should know about available skills; the user wants to configure which
  skills are always available; the agent doesn't seem to know about skills it should have.
  Triggers: list skills, what skills do I have, activate a skill, deactivate a skill,
  load my skills, auto-load skills, skill registry.
  Also use when: you need to check which skills are installed; you want to add or remove
  a skill from the auto-load list; a user asks what skills are available on this machine.
license: MIT
metadata:
  version: "1.0"
  category: productivity
  tools: auto-skill-loader
---

# auto-skill-loader

Give the agent persistent, automatic knowledge of your approved skills at session start. No manual triggering needed.

## How It Works

The MCP server exposes two things:
- **`skills://active`** resource — contains all your approved skills, read at session init
- **Tools** — for managing which skills are active

## Tools

### list_skills
Call `list_skills()` with no arguments. Returns all skills found in your skills directory with descriptions and active status.

Use when:
- User asks "what skills do I have installed"
- You need to see what's available before activating something

### activate_skill
Call `activate_skill(name="skill-name")` to add a skill to the auto-load list. The skill must already be in your skills directory.

Use when:
- User wants to add a skill to their approved list
- A skill is installed but not auto-loading

### deactivate_skill
Call `deactivate_skill(name="skill-name")` to remove a skill from the auto-load list.

Use when:
- User wants to stop a skill from auto-loading
- A skill is causing issues or conflicts

### suggest_skills
Call `suggest_skills()` with no arguments. If no skills are active, this scans available skills and suggests common ones to get started.

Use when:
- User has no skills configured yet and needs help getting started
- First session on a fresh machine

## On Session Start

At session start, the host (OpenCode/Claude Code/etc.) reads `skills://active`. This resource contains all skills currently in your `config.yaml` active list, concatenated together. The agent gets them injected automatically — no action needed from you.

If you make changes via `activate_skill` or `deactivate_skill`, they persist to `config.yaml` and will be active on next session.

## No Explicit Triggering

Unlike skills that require `skill({ name: "..." })` calls, auto-skill-loader works because:
1. The host reads `skills://active` at session init
2. Your approved skills are already in context before you say anything
3. The agent can reason about them without special invocation

## Example Workflows

### New user — first time setup
```
You: "what skills do I have?"
Agent: list_skills()
  → returns: vision-analysis, context-maintainer, markdown-mcp, etc.
You: "activate vision-analysis and context-maintainer"
Agent: activate_skill(name="vision-analysis")
  → ✅ Activated
  activate_skill(name="context-maintainer")
  → ✅ Activated
Agent: "Done! Both skills are now in your auto-load list. Restart the session to use them."
```

### Check what's active
```
You: "which skills are auto-loading?"
Agent: get_active_skills()
  → returns list of currently active skill names
```

### Remove a skill
```
You: "stop loading the markdown-mcp skill"
Agent: deactivate_skill(name="markdown-mcp")
  → ✅ Deactivated
```
