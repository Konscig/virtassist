#!/usr/bin/env python3
"""Auto-annotate dataset with LLM - wrapper script."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

if __name__ == "__main__":
    from benchmarks.auto_annotate import main

    main()
