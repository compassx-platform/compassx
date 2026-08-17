"""Python code execution sandbox — subprocess isolation (v1).

# TODO(v2): Replace subprocess isolation with Docker container execution.
# Current subprocess approach lacks full syscall/network isolation.
# LLM-generated code MUST NOT be trusted without container-level sandboxing.
# Upgrade path:
#   1. Install docker>=7.0.0
#   2. Pull a minimal Python image (python:3.11-slim)
#   3. docker run --rm --network none --memory 256m --cpus 0.5 python:3.11-slim
#      python -c "<code>"
# Tracked: architecture/agents-implementation-plan.md §Sandbox

Constraints enforced by this v1 implementation:
  - 30-second wall-clock timeout
  - 512 KB stdout cap
  - Temp working directory isolated per execution
  - stdin closed (no interactive input)
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
import textwrap
from typing import Any

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 30
_MAX_OUTPUT_BYTES = 512 * 1024  # 512 KB

# Packages the generated code is allowed to import.
# We don't enforce this at subprocess level (would require a custom importer),
# but it's documented here for future Docker allowlist enforcement.
ALLOWED_PACKAGES = frozenset({"pandas", "numpy", "matplotlib", "json", "math", "datetime", "re", "os", "sys"})


def run_python(code: str) -> dict[str, Any]:
    """
    Execute Python code in a sandboxed subprocess.

    Returns:
        {
            "stdout": str,
            "stderr": str,
            "exit_code": int,
            "truncated": bool,
        }
    """
    with tempfile.TemporaryDirectory(prefix="agent_py_") as tmpdir:
        script_path = os.path.join(tmpdir, "script.py")

        # Wrap code to cap output size
        wrapped = textwrap.dedent(f"""\
            import sys
            import io

            _orig_stdout = sys.stdout
            _orig_stderr = sys.stderr
            sys.stdout = io.StringIO()
            sys.stderr = io.StringIO()

            try:
                exec(compile({repr(code)}, '<agent_script>', 'exec'), {{'__name__': '__main__'}})
            except Exception as _e:
                print(f"Error: {{_e}}", file=sys.stderr)
            finally:
                _out = sys.stdout.getvalue()
                _err = sys.stderr.getvalue()
                sys.stdout = _orig_stdout
                sys.stderr = _orig_stderr
                print(_out, end='')
                print(_err, end='', file=sys.stderr)
        """)

        with open(script_path, "w", encoding="utf-8") as f:
            f.write(wrapped)

        try:
            proc = subprocess.run(
                [sys.executable, script_path],
                cwd=tmpdir,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=_TIMEOUT_SECONDS,
            )
            stdout = proc.stdout[:_MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")
            stderr = proc.stderr[:_MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")
            truncated = len(proc.stdout) > _MAX_OUTPUT_BYTES or len(proc.stderr) > _MAX_OUTPUT_BYTES

            return {
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": proc.returncode,
                "truncated": truncated,
            }
        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": f"Execution timed out after {_TIMEOUT_SECONDS} seconds.",
                "exit_code": -1,
                "truncated": False,
            }
        except Exception as exc:
            logger.exception("Python sandbox execution failed")
            return {
                "stdout": "",
                "stderr": f"Sandbox error: {exc}",
                "exit_code": -1,
                "truncated": False,
            }
