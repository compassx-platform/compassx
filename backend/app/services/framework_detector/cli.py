"""CLI entrypoint for standalone framework detection.

Usage:
    python3 -m app.services.framework_detector.cli /path/to/repo
    python3 detect_framework.py /path/to/repo
"""

import sys
import json
import os

# Support running directly as a standalone script without package installation
if __name__ == "__main__" and __package__ is None:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    from app.services.framework_detector.detector import detect_framework
else:
    from .detector import detect_framework


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    res = detect_framework(target)
    print(json.dumps(res, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
