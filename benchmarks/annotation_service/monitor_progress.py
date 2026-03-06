#!/usr/bin/env python3
"""Monitor annotation progress in real time."""

import json
import logging
import sys
from pathlib import Path
from datetime import datetime
import time

logger = logging.getLogger(__name__)


def format_time(seconds):
    """Format seconds to human readable time."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.1f}min"
    else:
        return f"{seconds / 3600:.1f}h"


def load_annotations(path):
    """Load annotations and return stats."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            items = json.load(f)

        total = len(items)
        annotated = sum(
            1 for item in items if item.get("annotate_is_small_talk") is not None
        )

        return {
            "total": total,
            "annotated": annotated,
            "remaining": total - annotated,
            "progress": annotated * 100 / total if total > 0 else 0,
            "items": items,
        }
    except FileNotFoundError:
        return None


def get_last_annotated_time(items):
    """Get timestamp of last annotation from file modification time."""
    try:
        file_path = (
            Path(__file__).parent
            / "dataset_from_20250601_to_20260228_20260303_082311_annotated_annotated.json"
        )
        return file_path.stat().st_mtime
    except FileNotFoundError:
        return None


def print_progress(stats, speed=None, eta=None):
    """Print progress bar with stats."""
    total = stats["total"]
    annotated = stats["annotated"]
    progress = stats["progress"]
    remaining = stats["remaining"]

    # Build output as single line with padding
    line = f"Progress: {progress:.1f}% ({annotated}/{total})  Remaining: {remaining} questions"

    if speed:
        line += f"  Speed: {speed:.3f} questions/sec ({speed * 60:.1f} questions/min)"

    if eta:
        line += f"  ETA: {format_time(eta)}"

    # Print on same line with padding to overwrite previous output
    print(f"\r{line:<120}", end="", flush=True)


def main():
    """Main monitoring loop."""
    # Auto-detect the annotated file in data/ directory
    data_dir = Path(__file__).parent / "data"

    # Find files ending with _annotated.json
    annotated_files = list(data_dir.glob("*_annotated.json"))

    if not annotated_files:
        print("No annotated files found in data/ directory")
        return

    # Use the most recently modified file
    output_path = max(annotated_files, key=lambda p: p.stat().st_mtime)

    # Find corresponding input file (without _annotated suffix)
    if "_annotated.json" in str(output_path):
        input_path = output_path.with_name(
            output_path.stem.replace("_annotated", "") + ".json"
        )
    else:
        input_path = output_path

    print("Starting annotation monitor...")
    print(f"Monitoring: {output_path}")
    print(f"Press Ctrl+C to stop\n")

    start_time = time.time()
    last_annotated = 0
    last_time = start_time

    try:
        while True:
            stats = load_annotations(output_path)

            if not stats:
                print("\rNo annotated file found yet. Waiting...")
                time.sleep(1)
                continue

            # Calculate speed
            current_time = time.time()
            current_annotated = stats["annotated"]

            if current_annotated > last_annotated:
                # New annotations since last check
                time_diff = current_time - last_time
                if time_diff > 0:
                    speed = (current_annotated - last_annotated) / time_diff
                    total_time = current_time - start_time
                    avg_speed = current_annotated / total_time if total_time > 0 else 0

                    # Calculate ETA
                    remaining = stats["remaining"]
                    eta = remaining / avg_speed if avg_speed > 0 else None

                    print_progress(stats, speed=speed, eta=eta)

                    last_annotated = current_annotated
                    last_time = current_time
            else:
                # No new annotations, just show progress
                total_time = current_time - start_time
                if total_time > 0:
                    avg_speed = current_annotated / total_time
                    remaining = stats["remaining"]
                    eta = remaining / avg_speed if avg_speed > 0 else None
                    print_progress(stats, speed=avg_speed, eta=eta)

            # Check if completed
            if stats["remaining"] == 0:
                print("\n\nANNOTATION COMPLETED!")
                total_time = time.time() - start_time
                print(f"Total time: {format_time(total_time)}")
                print(
                    f"Average speed: {stats['annotated'] / total_time:.3f} questions/sec"
                )
                break

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\nMonitor stopped by user")
    finally:
        pass


if __name__ == "__main__":
    main()
