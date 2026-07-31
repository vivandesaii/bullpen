"""
Standalone import diagnostic — isolates whether the app fails at
import time (bad config, missing dependency, circular import) versus
failing later once uvicorn tries to actually serve it.

Usage: python -u -m app.check_import
"""

import sys
import traceback

try:
    import app.main  # noqa: F401
    print("OK: app.main imported successfully", flush=True)
    sys.exit(0)
except Exception:
    print("IMPORT FAILED:", file=sys.stderr, flush=True)
    traceback.print_exc()
    sys.stderr.flush()
    sys.exit(1)
