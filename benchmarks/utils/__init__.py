"""Утилиты для бенчмарков."""

__version__ = "1.0.0"

from benchmarks.utils.tta_metrics import (
    measure_time,
    measure_async_time,
    compute_percentiles,
    compute_statistics,
    TTAMetricsCollector,
    TTATimingContext,
)

__all__ = [
    "measure_time",
    "measure_async_time",
    "compute_percentiles",
    "compute_statistics",
    "TTAMetricsCollector",
    "TTATimingContext",
]
