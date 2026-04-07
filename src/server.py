#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
auto-skill-loader — MCP server that auto-loads approved skills into agent sessions.

How it works:
1. User maintains config.yaml listing their approved skills
2. Server reads skill files from skills_dir (symlinks to ~/.config/opencode/skills/ etc.)
3. skills://active resource exposes all approved skill contents at session start
4. Agent gets all approved skills auto-injected — no explicit trigger needed

Security: Only skills explicitly listed in config.yaml are loaded.
No network fetches, no untrusted sources.
"""

import os
import sys
import yaml
import pathlib
from datetime import datetime

try:
    from mcp.server import Server
    from mcp.types import Resource, Tool, TextContent
except ImportError:
    print("ERROR: mcp package not installed. Run: pip install mcp", file=sys.stderr)
    sys.exit(1)

DEFAULT_CONFIG_PATH = (
    pathlib.Path.home() / ".config" / "auto-skill-loader" / "config.yaml"
)
DEFAULT_SKILLS_DIR = pathlib.Path.home() / ".config" / "opencode" / "skills"


def load_config(config_path: pathlib.Path) -> dict:
    """Load and validate config.yaml."""
    if not config_path.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        default_config = {
            "active_skills": [],
            "skills_dir": str(DEFAULT_SKILLS_DIR),
            "version": "1.0",
        }
        with open(config_path, "w") as f:
            yaml.dump(default_config, f)
        return default_config

    with open(config_path) as f:
        config = yaml.safe_load(f)

    if config is None:
        config = {
            "active_skills": [],
            "skills_dir": str(DEFAULT_SKILLS_DIR),
            "version": "1.0",
        }

    if "active_skills" not in config:
        config["active_skills"] = []
    if "skills_dir" not in config:
        config["skills_dir"] = str(DEFAULT_SKILLS_DIR)

    return config


def save_config(config_path: pathlib.Path, config: dict) -> None:
    """Save config back to disk."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


def get_skills_dir(config: dict) -> pathlib.Path:
    """Resolve skills directory path."""
    path = pathlib.Path(config.get("skills_dir", str(DEFAULT_SKILLS_DIR)))
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    return path


def read_skill_content(skills_dir: pathlib.Path, skill_name: str) -> str | None:
    """Read a skill's SKILL.md content."""
    skill_path = skills_dir / skill_name / "SKILL.md"
    if skill_path.exists() and skill_path.is_file():
        return skill_path.read_text(encoding="utf-8")

    alt_path = skills_dir / f"{skill_name}.md"
    if alt_path.exists() and alt_path.is_file():
        return alt_path.read_text(encoding="utf-8")

    return None


def build_active_skills_content(config: dict) -> str:
    """Build the combined skills://active resource content."""
    skills_dir = get_skills_dir(config)
    active = config.get("active_skills", [])

    if not active:
        return "# No active skills configured.\n# Add skills to ~/.config/auto-skill-loader/config.yaml\n# Or use activate_skill(name) to add them.\n"

    parts = []
    for skill in active:
        content = read_skill_content(skills_dir, skill)
        if content:
            parts.append(f"---\n# Skill: {skill}\n{content}")
        else:
            parts.append(
                f"---\n# Skill: {skill}\n# (SKILL.md not found — check config or skill name)"
            )

    return "\n\n".join(parts)


def list_available_skills(config: dict) -> list[dict]:
    """List all skills found in skills_dir, marking which are active."""
    skills_dir = get_skills_dir(config)
    active = set(config.get("active_skills", []))
    available = []

    if not skills_dir.exists():
        return available

    for entry in sorted(skills_dir.iterdir()):
        if entry.is_dir() and (entry / "SKILL.md").exists():
            skill_name = entry.name
            frontmatter = parse_skill_frontmatter(entry / "SKILL.md")
            available.append(
                {
                    "name": skill_name,
                    "description": frontmatter.get("description", "No description"),
                    "active": skill_name in active,
                    "path": str(entry),
                }
            )
        elif entry.is_file() and entry.suffix == ".md":
            skill_name = entry.stem
            frontmatter = parse_skill_frontmatter(entry)
            available.append(
                {
                    "name": skill_name,
                    "description": frontmatter.get("description", "No description"),
                    "active": skill_name in active,
                    "path": str(entry),
                }
            )

    return available


def parse_skill_frontmatter(skill_md_path: pathlib.Path) -> dict:
    """Extract YAML frontmatter from a SKILL.md file."""
    try:
        content = skill_md_path.read_text(encoding="utf-8")
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                return yaml.safe_load(parts[1]) or {}
    except Exception:
        pass
    return {}


def check_skill_prerequisites(config: dict, skill_name: str) -> str:
    """Check if a skill's prerequisites are met."""
    skills_dir = get_skills_dir(config)
    skill_path = skills_dir / skill_name / "SKILL.md"

    if not skill_path.exists():
        return f"❌ FAIL: Skill '{skill_name}' not found at {skill_path}\n  → Check that the skill is installed and active in config.yaml"

    try:
        content = skill_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"❌ FAIL: Cannot read skill file: {e}"

    checks = []
    all_passed = True

    checks.append(("Skill file exists", True, ""))

    frontmatter = parse_skill_frontmatter(skill_path)
    if frontmatter:
        checks.append(("Valid SKILL.md frontmatter", True, f"name={frontmatter.get('name', '?')}, version={frontmatter.get('metadata', {}).get('version', '?')}"))

    if "minimax" in skill_name.lower() or "vision" in skill_name.lower():
        mcp_check = check_minimax_mcp()
        checks.append(("MiniMax MCP (minimax-coding-plan-mcp)", mcp_check["passed"], mcp_check["message"]))
        if not mcp_check["passed"]:
            all_passed = False

    if "minimax" in skill_name.lower() or "vision" in skill_name.lower():
        key_check = check_api_key()
        checks.append(("MINIMAX_API_KEY configured", key_check["passed"], key_check["message"]))
        if not key_check["passed"]:
            all_passed = False

    lines = [f"# Prerequisite Check: {skill_name}"]
    lines.append("")
    for desc, passed, msg in checks:
        status = "✅" if passed else "❌"
        line = f"{status} {desc}"
        if msg:
            line += f" — {msg}"
        lines.append(line)

    lines.append("")
    if all_passed:
        lines.append("🎉 All prerequisites met! The skill should work correctly.")
    else:
        lines.append("⚠️  Some prerequisites are not met. Fix the issues above before using this skill.")

    return "\n".join(lines)


def check_minimax_mcp() -> dict:
    """Check if MiniMax MCP server is likely available."""
    try:
        import subprocess
        result = subprocess.run(
            ["uvx", "minimax-coding-plan-mcp", "--help"],
            capture_output=True,
            timeout=10,
            text=True
        )
        if result.returncode == 0 or "minimax" in result.stdout.lower() or "minimax" in result.stderr.lower():
            return {"passed": True, "message": "uvx found, MCP server can be launched"}
    except FileNotFoundError:
        pass
    except Exception:
        pass

    try:
        result = subprocess.run(
            ["which", "minimax-coding-plan-mcp"],
            capture_output=True,
            timeout=5,
            text=True
        )
        if result.returncode == 0:
            return {"passed": True, "message": "minimax-coding-plan-mcp found in PATH"}
    except Exception:
        pass

    return {
        "passed": False,
        "message": "uvx not found and minimax-coding-plan-mcp not in PATH. Install: curl -LsSf https://astral.sh/uv/install.sh | sh && uvx install minimax-coding-plan-mcp"
    }


def check_api_key() -> dict:
    """Check if MINIMAX_API_KEY is configured in the environment or config."""
    key = os.environ.get("MINIMAX_API_KEY", "")
    if key:
        masked = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
        return {"passed": True, "message": f"found (starts with {masked})"}

    config_path = pathlib.Path(os.environ.get("AUTO_SKILL_LOADER_CONFIG", str(DEFAULT_CONFIG_PATH)))
    if config_path.exists():
        config = load_config(config_path)
        if config.get("minimax_api_key"):
            return {"passed": True, "message": "found in config.yaml"}

    return {"passed": False, "message": "MINIMAX_API_KEY not set. Add it to your OpenCode MCP config under MiniMax.environment"}


def create_app():
    config_path = pathlib.Path(
        os.environ.get("AUTO_SKILL_LOADER_CONFIG", str(DEFAULT_CONFIG_PATH))
    )

    app = Server("auto-skill-loader")

    @app.list_resources()
    async def list_resources():
        config = load_config(config_path)
        content = build_active_skills_content(config)
        return [
            Resource(
                uri="skills://active",
                name="Active Skills",
                mime_type="text/markdown",
                description="All skills approved by the user for auto-loading at session start",
            ),
            Resource(
                uri="skills://config",
                name="Skill Configuration",
                mime_type="text/yaml",
                description="Current config.yaml content showing active skills and settings",
            ),
        ]

    @app.read_resource()
    async def read_resource(uri: str):
        config = load_config(config_path)

        if uri == "skills://active":
            return [TextContent(type="text", text=build_active_skills_content(config))]
        elif uri == "skills://config":
            config_text = yaml.dump(config, default_flow_style=False)
            return [TextContent(type="text", text=config_text)]
        else:
            raise ValueError(f"Unknown resource: {uri}")

    @app.list_tools()
    async def list_tools():
        return [
            Tool(
                name="list_skills",
                description="List all available skills found in skills_dir. Shows name, description, active status, and path.",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="activate_skill",
                description="Add a skill to the user's approved list. Persists to config.yaml.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name of the skill to activate",
                        },
                    },
                    "required": ["name"],
                },
            ),
            Tool(
                name="deactivate_skill",
                description="Remove a skill from the user's approved list. Persists to config.yaml.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name of the skill to deactivate",
                        },
                    },
                    "required": ["name"],
                },
            ),
            Tool(
                name="get_skill_info",
                description="Get detailed info about a specific skill.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Name of the skill"},
                    },
                    "required": ["name"],
                },
            ),
            Tool(
                name="get_active_skills",
                description="Get the list of currently active skill names.",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="suggest_skills",
                description="Suggests skills to activate when user has none configured.",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="check_prerequisites",
                description="Check if a skill's prerequisites are met. Validates MCP tool availability, API keys, and configuration. Returns pass/fail with specific error details.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "skill_name": {
                            "type": "string",
                            "description": "Name of the skill to check prerequisites for",
                        },
                    },
                    "required": ["skill_name"],
                },
            ),
        ]

    @app.call_tool()
    async def call_tool(name: str, arguments: dict):
        config = load_config(config_path)
        active = config.get("active_skills", [])

        if name == "list_skills":
            skills = list_available_skills(config)
            if not skills:
                return [
                    TextContent(
                        type="text",
                        text=f"No skills found in {config.get('skills_dir')}.\nAdd skills there or configure a different skills_dir in config.yaml.",
                    )
                ]
            lines = [f"# Available Skills ({len(skills)} found)\n"]
            for s in skills:
                status = "✅ active" if s["active"] else "○ inactive"
                lines.append(
                    f"- **{s['name']}** ({status})\n  {s['description']}\n  path: {s['path']}\n"
                )
            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "activate_skill":
            skill_name = arguments["name"]
            available = list_available_skills(config)
            available_names = [s["name"] for s in available]

            if skill_name not in available_names:
                found = [
                    s["name"]
                    for s in available
                    if skill_name.lower() in s["name"].lower()
                ]
                if found:
                    return [
                        TextContent(
                            type="text",
                            text=f"Skill '{skill_name}' not found. Did you mean: {', '.join(found)}",
                        )
                    ]
                return [
                    TextContent(
                        type="text",
                        text=f"Skill '{skill_name}' not found. Available: {', '.join(available_names)}",
                    )
                ]

            if skill_name in active:
                return [
                    TextContent(type="text", text=f"'{skill_name}' is already active.")
                ]

            active.append(skill_name)
            config["active_skills"] = active
            save_config(config_path, config)
            return [
                TextContent(
                    type="text",
                    text=f"✅ Activated '{skill_name}'. It will be auto-loaded at next session start.",
                )
            ]

        elif name == "deactivate_skill":
            skill_name = arguments["name"]
            if skill_name not in active:
                return [
                    TextContent(
                        type="text", text=f"'{skill_name}' is not currently active."
                    )
                ]

            active.remove(skill_name)
            config["active_skills"] = active
            save_config(config_path, config)
            return [
                TextContent(
                    type="text",
                    text=f"✅ Deactivated '{skill_name}'. It will no longer be auto-loaded.",
                )
            ]

        elif name == "get_skill_info":
            skill_name = arguments["name"]
            available = list_available_skills(config)
            skill = next((s for s in available if s["name"] == skill_name), None)
            if not skill:
                return [
                    TextContent(type="text", text=f"Skill '{skill_name}' not found.")
                ]
            return [
                TextContent(
                    type="text", text=yaml.dump(skill, default_flow_style=False)
                )
            ]

        elif name == "get_active_skills":
            if not active:
                return [
                    TextContent(
                        type="text",
                        text="No active skills. Use list_skills to see available, then activate_skill to add some.",
                    )
                ]
            lines = [f"# Active Skills ({len(active)})\n"] + [f"- {n}" for n in active]
            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "suggest_skills":
            available = list_available_skills(config)
            if not available:
                return [
                    TextContent(
                        type="text",
                        text="No skills found in your skills_dir.\nInstall some skills from skills.sh or create your own SKILL.md files.",
                    )
                ]
            if active:
                return [
                    TextContent(
                        type="text",
                        text=f"You already have {len(active)} active skills: {', '.join(active)}\nUse list_skills to see all available.",
                    )
                ]

            suggestions = []
            common_patterns = [
                "vision",
                "context",
                "markdown",
                "pdf",
                "docx",
                "xlsx",
                "code-review",
                "git",
            ]
            for s in available:
                if any(p in s["name"].lower() for p in common_patterns):
                    suggestions.append(s["name"])

            suggested = (
                suggestions[:6] if suggestions else [s["name"] for s in available[:6]]
            )
            return [
                TextContent(
                    type="text",
                    text=f"# Getting Started\nYou have {len(available)} skills available but none are active yet.\n\nSuggested skills to activate:\n"
                    + "\n".join(f"- {n}" for n in suggested)
                    + f"\n\nTo activate: activate_skill(name='skill-name')",
                )
            ]

        elif name == "check_prerequisites":
            skill_name = arguments["skill_name"]
            result = check_skill_prerequisites(config, skill_name)
            return [TextContent(type="text", text=result)]

        else:
            raise ValueError(f"Unknown tool: {name}")

    return app


if __name__ == "__main__":
    import mcp.server.stdio
    import asyncio

    async def run():
        app = create_app()
        async with mcp.server.stdio.stdio_server() as streams:
            await app.run(streams[0], streams[1], app.create_initialization_options())

    asyncio.run(run())
