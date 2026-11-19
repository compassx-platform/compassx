"""Nova package refresh and canvas prompt."""
import unittest
from unittest.mock import MagicMock

from app.agent_runtime.sandbox_controller import NovaSandboxController
from sandbox_nova.prompt import SYSTEM_PROMPT


class TestNovaPackage(unittest.TestCase):
    def test_prompt_tells_nova_when_to_write_a_canvas(self):
        self.assertIn("/workspace/.canvases/", SYSTEM_PROMPT)
        self.assertIn("compassx/canvas", SYSTEM_PROMPT)
        self.assertIn("metrics breakdown", SYSTEM_PROMPT)
        self.assertIn("several canvases", SYSTEM_PROMPT)
        self.assertNotIn("create_plan", SYSTEM_PROMPT)

    def test_matching_package_version_skips_install(self):
        calls = []

        def exec_fn(sandbox_id, command, timeout=10, env=None):
            calls.append(env)
            result = MagicMock()
            result.success = True
            result.stdout = "modes-2\n"
            result.stderr = ""
            return result

        refreshed = NovaSandboxController()._ensure_package("sb", exec_fn)
        self.assertFalse(refreshed)
        self.assertEqual(calls, [None])

    def test_older_package_is_reinstalled(self):
        calls = []

        def exec_fn(sandbox_id, command, timeout=10, env=None):
            calls.append(env)
            result = MagicMock()
            result.success = True
            result.stdout = "ok" if env else "0\n"
            result.stderr = ""
            return result

        refreshed = NovaSandboxController()._ensure_package("sb", exec_fn)
        self.assertTrue(refreshed)
        self.assertIsNone(calls[0])
        self.assertIn("NOVA_PKG", calls[1])
