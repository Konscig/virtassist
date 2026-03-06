"""Утилиты для измерения метрик Time To Answer (TTA).

Предоставляет декораторы и классы для измерения времени выполнения
различных компонентов RAG-системы.
"""

import functools
import logging
import time
from typing import Any, Callable, Dict, List, Optional
import numpy as np

logger = logging.getLogger(__name__)


def measure_time(
    metric_name: Optional[str] = None,
) -> Callable:
    """Декоратор для измерения времени выполнения функции.

    Args:
        metric_name: Имя метрики для логирования (по умолчанию имя функции)

    Returns:
        Декорированная функция с измерением времени

    Example:
        @measure_time("cache_search")
        def find_similar_question(question: str):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            name = metric_name or func.__name__
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                logger.debug(f"{name}: {elapsed_ms:.2f}ms")
                return result, elapsed_ms
            except Exception as e:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                logger.error(f"{name} failed after {elapsed_ms:.2f}ms: {e}")
                raise

        return wrapper

    return decorator


async def measure_async_time(
    metric_name: Optional[str] = None,
) -> Callable:
    """Декоратор для измерения времени выполнения асинхронной функции.

    Args:
        metric_name: Имя метрики для логирования (по умолчанию имя функции)

    Returns:
        Декорированная асинхронная функция с измерением времени
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            name = metric_name or func.__name__
            start_time = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                logger.debug(f"{name}: {elapsed_ms:.2f}ms")
                return result, elapsed_ms
            except Exception as e:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                logger.error(f"{name} failed after {elapsed_ms:.2f}ms: {e}")
                raise

        return wrapper

    return decorator


def compute_percentiles(
    values: List[float],
    percentiles: List[int] = [50, 90, 95, 99],
) -> Dict[str, float]:
    """Вычислить перцентили для списка значений.

    Args:
        values: Список значений в миллисекундах
        percentiles: Список перцентилей для вычисления

    Returns:
        Словарь с перцентилями {P50: ..., P90: ..., P95: ..., P99: ...}
    """
    if not values:
        return {f"P{p}": 0.0 for p in percentiles}

    values_array = np.array(values)
    result = {}
    for p in percentiles:
        result[f"P{p}"] = float(np.percentile(values_array, p))

    return result


def compute_statistics(values: List[float]) -> Dict[str, float]:
    """Вычислить базовую статистику для списка значений.

    Args:
        values: Список значений в миллисекундах

    Returns:
        Словарь со статистикой {mean, std, min, max, count}
    """
    if not values:
        return {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0, "count": 0}

    values_array = np.array(values)
    return {
        "mean": float(np.mean(values_array)),
        "std": float(np.std(values_array)),
        "min": float(np.min(values_array)),
        "max": float(np.max(values_array)),
        "count": len(values),
    }


class TTAMetricsCollector:
    """Коллектор для сбора метрик Time To Answer.

    Собирает временные метрики для различных этапов обработки запроса
    и вычисляет агрегированную статистику.
    """

    def __init__(self):
        """Инициализировать коллектор."""
        self.metrics: Dict[str, List[float]] = {}

    def record(self, metric_name: str, value_ms: float) -> None:
        """Записать значение метрики.

        Args:
            metric_name: Имя метрики
            value_ms: Значение в миллисекундах
        """
        if metric_name not in self.metrics:
            self.metrics[metric_name] = []
        self.metrics[metric_name].append(value_ms)

    def get_values(self, metric_name: str) -> List[float]:
        """Получить все значения для метрики.

        Args:
            metric_name: Имя метрики

        Returns:
            Список значений
        """
        return self.metrics.get(metric_name, [])

    def get_statistics(
        self, metric_name: str, include_percentiles: bool = True
    ) -> Dict[str, float]:
        """Получить статистику для метрики.

        Args:
            metric_name: Имя метрики
            include_percentiles: Включать ли перцентили

        Returns:
            Словарь со статистикой
        """
        values = self.get_values(metric_name)
        stats = compute_statistics(values)

        if include_percentiles:
            percentiles = compute_percentiles(values)
            stats.update(percentiles)

        return stats

    def get_all_metrics(self) -> Dict[str, Dict[str, float]]:
        """Получить статистику для всех метрик.

        Returns:
            Словарь {имя_метрики: {статистика}}
        """
        result = {}
        for metric_name in self.metrics:
            result[metric_name] = self.get_statistics(metric_name)
        return result

    def get_summary(self) -> Dict[str, Any]:
        """Получить сводную статистику по всем метрикам.

        Returns:
            Словарь с агрегированной информацией
        """
        summary = {"total_measurements": sum(len(v) for v in self.metrics.values())}

        for metric_name, values in self.metrics.items():
            if values:
                summary[f"{metric_name}_count"] = len(values)
                summary[f"{metric_name}_total_ms"] = sum(values)
                summary[f"{metric_name}_avg_ms"] = sum(values) / len(values)

        return summary

    def clear(self) -> None:
        """Очистить все накопленные метрики."""
        self.metrics.clear()

    def to_dict(self) -> Dict[str, List[float]]:
        """Экспортировать метрики в словарь.

        Returns:
            Словарь {имя_метрики: [значения]}
        """
        return self.metrics.copy()


class TTATimingContext:
    """Контекстный менеджер для измерения времени выполнения блока кода.

    Example:
        with TTATimingContext(collector, "db_query") as timing:
            result = database.execute(query)
    """

    def __init__(self, collector: TTAMetricsCollector, metric_name: str):
        """Инициализировать контекст.

        Args:
            collector: Коллектор метрик
            metric_name: Имя метрики
        """
        self.collector = collector
        self.metric_name = metric_name
        self.start_time: Optional[float] = None
        self.elapsed_ms: float = 0.0

    def __enter__(self) -> "TTATimingContext":
        """Начать измерение."""
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Закончить измерение и записать результат."""
        if self.start_time is not None:
            self.elapsed_ms = (time.perf_counter() - self.start_time) * 1000
            self.collector.record(self.metric_name, self.elapsed_ms)

    def get_elapsed_ms(self) -> float:
        """Получить время выполнения.

        Returns:
            Время в миллисекундах
        """
        return self.elapsed_ms
