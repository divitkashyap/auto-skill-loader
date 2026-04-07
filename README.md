# auto-skill-loader

**Give your AI agent a persistent skill library it auto-loads at session start.**

auto-skill-loader is an MCP server that exposes your pre-approved skills via a `skills://active` resource. Instead of manually invoking skills or relying on fuzzy pattern matching, your agent reads this resource at session startup and automatically has all your approved skills in context.

## How it works

1. **You configure** which skills to auto-load in `~/.config/auto-skill-loader/config.yaml`
2. **The MCP server** reads skill files from your skills directory and exposes them via `skills://active`
3. **At session start** your agent reads `skills://active` and gets all approved skills auto-injected
4. **No explicit triggers needed** — the agent already knows your skills

## Why

Most skill systems require the agent to:
- Explicitly call a `use_skill` tool, or
- Guess based on conversation patterns (unreliable)

auto-skill-loader solves this by using the MCP **resource at session init** pattern — deterministic, no guessing.

## Installation

### Option 1: uvx (recommended — no install needed)

```bash
uvx auto-skill-loader
```

### Option 2: pip

```bash
pip install auto-skill-loader
auto-skill-loader
```

### Option 3: Build from source

```bash
git clone https://github.com/divitkashyap/auto-skill-loader.git
cd auto-skill-loader
pip install -e .
auto-skill-loader
```

## Configuration

### OpenCode

Add to `~/.config/opencode/opencode.json`:

```json
{
  "mcp": {
    "auto-skill-loader": {
      "type": "local",
      "command": ["uvx", "auto-skill-loader"],
      "enabled": true
    }
  }
}
```

### Claude Code

```bash
claude mcp add -s user auto-skill-loader -- uvx auto-skill-loader -y
```

### Cursor

Add to your MCP settings:

```json
{
  "mcpServers": {
    "auto-skill-loader": {
      "command": "uvx",
      "args": ["auto-skill-loader"]
    }
  }
}
```

## Setup

1. Create skills directory (symlink to your existing skills):

```bash
mkdir -p ~/.config/auto-skill-loader
ln -sf ~/.config/opencode/skills ~/.config/auto-skill-loader/skills
```

2. Edit `~/.config/auto-skill-loader/config.yaml`:

```yaml
active_skills:
  - vision-analysis
  - context-maintainer
  - markdown-mcp
skills_dir: ~/.config/auto-skill-loader/skills
```

3. Restart your agent. It will now auto-load all listed skills at session start.

## Tools

| Tool | What it does |
|---|---|
| `list_skills` | List all available skills in skills_dir with descriptions |
| `activate_skill` | Add a skill to your approved list (persists to config.yaml) |
| `deactivate_skill` | Remove a skill from your approved list |
| `get_skill_info` | Get details about a specific skill |
| `get_active_skills` | List currently active skill names |
| `suggest_skills` | If no skills are active, suggests common ones to get started |

## Resources

| Resource | What it does |
|---|---|
| `skills://active` | All approved skill contents concatenated — read by host at session init |
| `skills://config` | Your current config.yaml content |

## Security

- **User-controlled** — only skills in `config.yaml` are loaded
- **No network fetches** — everything is local
- **No prompt injection** — skills come from your own configured directory

## Repo Structure

```
auto-skill-loader/
├── src/
│   └── server.py        # MCP server (Python stdlib + mcp package)
├── pyproject.toml       # Package config
├── README.md            # This file
├── SKILL.md             # For agent onboarding
└── LICENSE              # MIT
```

## Requirements

- Python 3.9+
- `mcp` package (`pip install mcp`)
- `pyyaml` package (`pip install pyyaml`)

Or just use `uvx auto-skill-loader` which fetches dependencies automatically.