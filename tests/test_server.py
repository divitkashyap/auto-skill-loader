"""Tests for auto-skill-loader server."""

import asyncio
import os
import pathlib
import subprocess
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "src"))

from auto_skill_loader.server import (
    check_api_key,
    check_skill_prerequisites,
    load_config,
    create_app,
    handle_minimax_tool,
)


class TestCheckApiKey(unittest.TestCase):
    """Test check_api_key() handles both MINIMAX_TOKEN_PLAN_KEY and MINIMAX_API_KEY."""

    def tearDown(self):
        for var in ["MINIMAX_TOKEN_PLAN_KEY", "MINIMAX_API_KEY"]:
            os.environ.pop(var, None)

    def test_checks_token_plan_key_first(self):
        """MINIMAX_TOKEN_PLAN_KEY should be found when set."""
        os.environ["MINIMAX_TOKEN_PLAN_KEY"] = "sk-cp-test-key-12345"
        result = check_api_key()
        self.assertTrue(result["passed"])
        self.assertIn("found", result["message"])

    def test_falls_back_to_api_key(self):
        """Should find MINIMAX_API_KEY when TOKEN_PLAN_KEY is not set."""
        os.environ["MINIMAX_API_KEY"] = "sk-cp-test-key-67890"
        result = check_api_key()
        self.assertTrue(result["passed"])
        self.assertIn("found", result["message"])

    def test_fails_when_neither_set(self):
        """Should fail gracefully when neither key is set."""
        result = check_api_key()
        self.assertFalse(result["passed"])
        self.assertIn("not set", result["message"])

    def test_error_message_mentions_token_plan_key(self):
        """Error message should guide users to set MINIMAX_TOKEN_PLAN_KEY."""
        result = check_api_key()
        self.assertIn("MINIMAX_TOKEN_PLAN_KEY", result["message"])


class TestCheckApiKeyEnvPriority(unittest.TestCase):
    """Test that MINIMAX_TOKEN_PLAN_KEY takes priority over MINIMAX_API_KEY."""

    def tearDown(self):
        os.environ.pop("MINIMAX_TOKEN_PLAN_KEY", None)
        os.environ.pop("MINIMAX_API_KEY", None)

    def test_token_plan_key_used_when_both_set(self):
        """When both are set, TOKEN_PLAN_KEY should be used (checked first)."""
        os.environ["MINIMAX_TOKEN_PLAN_KEY"] = "sk-cp-token-plan-key"
        os.environ["MINIMAX_API_KEY"] = "sk-cp-api-key"
        result = check_api_key()
        self.assertTrue(result["passed"])
        self.assertIn("sk-cp-to", result["message"])


class TestMinimaxToolSubprocess(unittest.TestCase):
    """Test handle_minimax_tool subprocess communication."""

    def tearDown(self):
        os.environ.pop("MINIMAX_TOKEN_PLAN_KEY", None)
        os.environ.pop("MINIMAX_API_HOST", None)

    @patch("subprocess.Popen")
    def test_uses_communicate_with_input(self, mock_popen):
        """Should use proc.communicate(input=...) not stdin.write()."""
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (
            b'{"jsonrpc":"2.0","id":"2","result":{"content":[{"type":"text","text":"test"}]}}',
            b"",
        )
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc
        os.environ["MINIMAX_TOKEN_PLAN_KEY"] = "sk-cp-test-key"

        async def run():
            return await handle_minimax_tool("test_tool", {"arg": "value"})

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(run())
        finally:
            loop.close()

        mock_proc.communicate.assert_called()
        call_kwargs = mock_proc.communicate.call_args
        self.assertIn("input", call_kwargs.kwargs)
        self.assertIsInstance(call_kwargs.kwargs["input"], bytes)
        self.assertIn(b"jsonrpc", call_kwargs.kwargs["input"])


class TestSkillPrerequisites(unittest.TestCase):
    """Test check_skill_prerequisites uses correct env var names."""

    def tearDown(self):
        os.environ.pop("MINIMAX_TOKEN_PLAN_KEY", None)
        os.environ.pop("MINIMAX_API_KEY", None)

    def test_vision_skill_checks_api_key(self):
        """Prerequisite check for vision skill should report API key status."""
        os.environ["MINIMAX_TOKEN_PLAN_KEY"] = "sk-cp-test-key"
        config = load_config(pathlib.Path(__file__).parent.parent / "config.yaml")
        result = check_skill_prerequisites(config, "vision-analysis")
        self.assertIn("MINIMAX", result)


class TestServerStartup(unittest.TestCase):
    """Test the MCP server can start."""

    def test_create_app_returns_server(self):
        """create_app should return a Server instance."""
        app = create_app()
        self.assertIsNotNone(app)
        self.assertEqual(app.name, "auto-skill-loader")


class TestConfigLoading(unittest.TestCase):
    """Test config.yaml loading."""

    def test_load_config_returns_dict(self):
        """Config should load and return a dict."""
        config = load_config(pathlib.Path(__file__).parent.parent / "config.yaml")
        self.assertIsInstance(config, dict)

    def test_config_has_active_skills(self):
        """Config should have active_skills list."""
        config = load_config(pathlib.Path(__file__).parent.parent / "config.yaml")
        self.assertIn("active_skills", config)


class TestSkillMetadataValidation(unittest.TestCase):
    """Test that our SKILL.md doesn't have invalid metadata fields."""

    def test_no_requires_mcp_in_own_skill(self):
        """Our own SKILL.md should not have requires_mcp which filters skills."""
        skill_path = pathlib.Path(__file__).parent.parent / "SKILL.md"
        if not skill_path.exists():
            self.skipTest("No SKILL.md in repo root")

        content = skill_path.read_text()
        fm = yaml_safe_load(content.split("---")[1])
        meta = fm.get("metadata", {})

        if "requires_mcp" in meta:
            self.fail("requires_mcp causes opencode-agent-skills to filter this skill")


def yaml_safe_load(text):
    """Minimal YAML loader without the pyyaml dependency requirement."""
    import re

    result = {}
    for line in text.strip().split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            val = val.strip().strip('"').strip("'")
            if val.startswith("[") and val.endswith("]"):
                continue
            if val:
                result[key.strip()] = val
    return {"metadata": result}


if __name__ == "__main__":
    unittest.main()
