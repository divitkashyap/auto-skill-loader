#!/usr/bin/env python3
"""Validate SKILL.md metadata doesn't have fields that break opencode-agent-skills."""

import pathlib
import sys
import yaml

errors = []

skill_path = pathlib.Path("skills/vision-analysis/SKILL.md")
if not skill_path.exists():
    print("SKILL.md not found at skills/vision-analysis/SKILL.md - skipping")
    sys.exit(0)

content = skill_path.read_text()
fm = yaml.safe_load(content.split("---")[1])
meta = fm.get("metadata", {})

if "requires_mcp" in meta:
    errors.append(
        "requires_mcp field causes opencode-agent-skills to filter this skill"
    )

if "sources" in meta and isinstance(meta.get("sources"), list):
    errors.append(
        "sources as list fails z.record(z.string(),z.string()) schema validation"
    )

if "allowed-tools" in meta and not isinstance(meta.get("allowed-tools"), list):
    errors.append("allowed-tools must be a list if present")

if errors:
    print("SKILL.md validation errors:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("SKILL.md metadata is valid")
    sys.exit(0)
