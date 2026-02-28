#!/usr/bin/env python3
"""Analyze annotated dataset - wrapper script."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

if __name__ == "__main__":
    from benchmarks.analyze_annotated import main

    main()
