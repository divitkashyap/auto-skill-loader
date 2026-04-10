# auto-skill-loader

**Give your AI agent a persistent skill library it auto-loads at session start.**

`mcp-name: io.github.divitkashyap/auto-skill-loader`

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

**Note:** Claude Code requires a specific JSON format via `add-json`:

```bash
claude mcp add-json -s user auto-skill-loader '{"type":"stdio","command":"/FULL/PATH/TO/python","args":["-m","server"],"env":{"MINIMAX_TOKEN_PLAN_KEY":"sk-cp-YOUR-KEY-HERE"}}'
```

Replace `/FULL/PATH/TO/python` with the path to your Python (e.g. `/Users/YOU/auto-skill-loader/.venv/bin/python`).

Or for uvx (requires network on first run):

```bash
claude mcp add -s user --transport stdio -e MINIMAX_TOKEN_PLAN_KEY=sk-cp-YOUR-KEY auto-skill-loader -- uvx auto-skill-loader
```

## Tested On

| Host | Status | Verified |
|---|---|---|
| Claude Code (macOS) | ✅ Working | Vision tool + skill loading + MiniMax-M2.7 model |
| OpenCode (macOS) | ✅ Working | Vision tool + skill loading + MiniMax Token Plan |

Other MCP-compatible hosts (Cursor, Zed, etc.) should work with the same configuration — contributions welcome.

## Platform Differences & Known Issues

### Image Input: OpenCode vs Claude Code

Both hosts work with `auto-skill-loader` vision tools, but image input behaves differently:

| Host | How images are passed | Recommended workflow |
|---|---|---|
| **Claude Code** | Images uploaded to URL automatically → tool receives URL | Paste image directly ✅ works |
| **OpenCode** | Inline images render visually but may not give tools a real path | Give a file path instead of pasting |

**OpenCode note:** When you paste an image in OpenCode, it may render inline but the agent sees it as a filename string (e.g. `logo.png`) rather than a real filesystem path. This is a known OpenCode rendering behavior.

**Workaround for OpenCode:** Instead of pasting, give the agent the actual file path:
```
analyze this image: /path/to/your/image.png
```

The agent can access local files directly in OpenCode. If the image is only in your clipboard, the agent can extract it to `/tmp/` first.

### What We're Monitoring

We actively track the following OpenCode issues:
- Inline image rendering (images pasted don't expose real paths to tools)
- MCP stdio transport for local servers (our proxy tools work around this)
- Session persistence of skills across restarts

If OpenCode releases a fix for inline image paths, this documentation will be updated.

### Other Known Issues

| Issue | Severity | Workaround |
|---|---|---|
| OpenCode inline images show as filename, not path | Medium — affects paste workflow | Use file paths instead |
| Claude Code auth conflict (ANTHROPIC_AUTH_TOKEN vs managed key) | Low — cosmetic warning | Harmless, can be ignored |
| First vision call may take 3-5s (uvx download) | Low — one-time | Subsequent calls are ~200ms |

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
| `check_prerequisites` | Validate a skill's dependencies (MCP tools, API keys, env vars) |

## Bonus: MiniMax Vision & Web Search Proxy

auto-skill-loader also exposes two tools that proxy to `minimax-coding-plan-mcp` with a **working stdio transport**:

| Tool | What it does |
|---|---|
| `minimax_understand_image` | Analyze images (JPEG, PNG, GIF, WebP up to 20MB) |
| `minimax_web_search` | Web search using MiniMax |

### The OpenCode MCP Bug

When OpenCode's built-in `minimax-coding-plan-mcp` MCP integration (`minimax-token-plan`) is configured, the `understand_image` tool fails with:

```
API Error: login fail: Please carry the API secret key in the 'Authorization' field
```

This happens even when:
- ✅ `MINIMAX_API_KEY` / `MINIMAX_TOKEN_PLAN_KEY` is set correctly
- ✅ API key is valid (same key works via direct API calls)
- ✅ Token Plan has available vision quota

**Root cause:** OpenCode's stdio transport for local MCP servers sends messages in a way that breaks the MCP protocol — likely batched writes without proper flush between JSON-RPC messages. Direct subprocess tests with sequential writes + flush() work fine.

**The fix:** Our proxy tools in auto-skill-loader use proper sequential stdio communication, bypassing OpenCode's broken transport layer.

### Setup

1. Set your MiniMax Token Plan key in `~/.config/opencode/.env`:
```bash
MINIMAX_TOKEN_PLAN_KEY=sk-cp-your-key-here
```

2. Add auto-skill-loader to `~/.config/opencode/opencode.json`:
```json
{
  "mcp": {
    "auto-skill-loader": {
      "type": "local",
      "command": ["/path/to/venv/bin/python", "-m", "server"],
      "enabled": true
    }
  }
}
```

3. **Critical:** If you have `minimax-coding-plan-mcp` configured directly in opencode.json (the `minimax-token-plan` entry), **remove or disable it** — its broken stdio transport will cause "login fail" errors. The proxy tools in auto-skill-loader replace it entirely.

4. Restart OpenCode and verify: `/ask Do you have auto-skill-loader_minimax_understand_image available?`

### Diagnosis

If you see "login fail" errors after setup:

1. **Disable the broken minimax MCP** — ensure `"minimax-token-plan": { "enabled": false }` or remove it entirely
2. **Restart OpenCode completely** — MCP servers are re-spawned on each session
3. **Check with:** `/ask Call minimax_understand_image with image_source="/any/real/image.png" and prompt="test"`

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