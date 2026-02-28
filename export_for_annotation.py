#!/usr/bin/env python3
"""Export Q&A for annotation - wrapper script."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

if __name__ == "__main__":
    from benchmarks.export_for_annotation import main

    main()
