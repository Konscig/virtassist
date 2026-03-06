#!/usr/bin/env python3
"""Annotate dataset with Ollama - wrapper script."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

if __name__ == "__main__":
    from benchmarks.annotate_with_ollama import main

    main()
