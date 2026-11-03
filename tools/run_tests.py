"""Run the complete suite and leave Qt cleanly on Windows."""
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from main import safe_exit_setup

if __name__ == "__main__":
    safe_exit_setup()
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    code = 0 if result.wasSuccessful() else 1
    sys.stdout.flush()
    sys.stderr.flush()
    # Live Qt application objects from UI tests must not be destructed after
    # the Windows text/input DLLs have already begun interpreter teardown.
    if sys.platform.startswith("win"):
        os._exit(code)
    sys.exit(code)
