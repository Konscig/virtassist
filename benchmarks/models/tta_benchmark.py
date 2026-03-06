"""Бенчмарк для измерения Time To Answer (TTA) в RAG-системе.

Реализует многоуровневое измерение времени генерации ответа:
- E2E: от момента отправки вопроса пользователем до получения ответа
- Компонентное измерение: время выполнения каждого этапа
- Инструментальное измерение: использование APM-подобных метрик
"""

import logging
import time
from typing import Any, Callable, Dict, List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

try:
    from qa.config import Config
    from qa.database import Chunk, QuestionAnswer
    from qa.confluence_retrieving import get_chunk
    from qa.main import get_answer, assess_answer
except ImportError:
    from config import Config
    from database import Chunk, QuestionAnswer
    from confluence_retrieving import get_chunk
    from main import get_answer, assess_answer

from benchmarks.utils.tta_metrics import TTAMetricsCollector, TTATimingContext

logger = logging.getLogger(__name__)


class TTABenchmark:
    """Бенчмарк для измерения Time To Answer.

    Измеряет время выполнения различных этапов обработки запроса в RAG-системе.

    Attributes:
        engine: Движок базы данных
        encoder: Модель для генерации эмбеддингов
        collector: Коллектор метрик TTA
    """

    def __init__(
        self,
        engine: Engine,
        encoder: SentenceTransformer,
    ):
        """Инициализировать TTA бенчмарк.

        Args:
            engine: Движок базы данных
            encoder: Модель для генерации эмбеддингов
        """
        self.engine = engine
        self.encoder = encoder
        self.collector = TTAMetricsCollector()
        logger.info("TTABenchmark инициализирован")

    def _measure_db_context_extraction(self, user_id: int) -> tuple[List[Any], float]:
        """Измерить время формирования контекста диалога из БД.

        Args:
            user_id: ID пользователя

        Returns:
            Кортеж (контекст, время в мс)
        """
        from chatbot.database import get_history_of_chat, filter_chat_history

        start_time = time.perf_counter()
        try:
            chat_history = get_history_of_chat(self.engine, user_id)
            answered_pairs, recent_unanswered = filter_chat_history(chat_history)
            dialog_context = []
            for qa in answered_pairs:
                dialog_context.append(f"Q: {qa.question}")
                dialog_context.append(f"A: {qa.answer}")
            for unanswered_question in recent_unanswered:
                dialog_context.append(f"Q: {unanswered_question.question}")
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return dialog_context, elapsed_ms
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Ошибка извлечения контекста: {e}")
            return [], elapsed_ms

    def _measure_cache_search(
        self, question: str
    ) -> tuple[Optional[tuple[str, str]], bool, float]:
        """Измерить время поиска в кэше (похожие вопросы).

        Args:
            question: Вопрос пользователя

        Returns:
            Кортеж ((answer, url), cache_hit, время в мс)
        """
        import asyncio
        from qa.main import find_similar_question

        start_time = time.perf_counter()
        try:
            result = asyncio.run(find_similar_question(self.encoder, question))
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            cache_hit = result is not None
            return result, cache_hit, elapsed_ms
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Ошибка поиска в кэше: {e}")
            return None, False, elapsed_ms

    def _measure_chunk_search(self, question: str) -> tuple[Optional[Chunk], float]:
        """Измерить время поиска чанка через pgvector.

        Args:
            question: Вопрос пользователя

        Returns:
            Кортеж (чанк, время в мс)
        """
        start_time = time.perf_counter()
        try:
            chunk = get_chunk(self.engine, self.encoder, question)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return chunk, elapsed_ms
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Ошибка поиска чанка: {e}")
            return None, elapsed_ms

    def _measure_llm_generation(
        self, dialog_history: List[str], knowledge_base: str, question: str
    ) -> tuple[str, float]:
        """Измерить время генерации ответа через LLM.

        Args:
            dialog_history: История диалога
            knowledge_base: Контекст (текст чанка)
            question: Вопрос

        Returns:
            Кортеж (ответ, время в мс)
        """
        start_time = time.perf_counter()
        try:
            answer = get_answer(dialog_history, knowledge_base, question)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return answer, elapsed_ms
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Ошибка генерации LLM: {e}")
            return "", elapsed_ms

    def _measure_judge_assessment(
        self,
        dialog_history: List[str],
        question: str,
        answer: str,
        content: str = "",
        generation: bool = False,
    ) -> tuple[bool, float]:
        """Измерить время оценки судьей.

        Args:
            dialog_history: История диалога
            question: Вопрос
            answer: Ответ
            content: Контент (для генерации)
            generation: Флаг генерации

        Returns:
            Кортеж (результат оценки, время в мс)
        """
        start_time = time.perf_counter()
        try:
            result = assess_answer(
                dialog_history, question, answer, content, generation
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return result, elapsed_ms
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Ошибка оценки судьей: {e}")
            return False, elapsed_ms

    def _measure_db_save(
        self, question: str, answer: str, confluence_url: Optional[str], user_id: int
    ) -> tuple[int, float]:
        """Измерить время сохранения в БД.

        Args:
            question: Вопрос
            answer: Ответ
            confluence_url: URL чанка
            user_id: ID пользователя

        Returns:
            Кортеж (ID записи, время в мс)
        """
        from chatbot.database import add_question_answer

        start_time = time.perf_counter()
        try:
            qa_id = add_question_answer(
                self.engine, question, answer, confluence_url, user_id
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return qa_id, elapsed_ms
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Ошибка сохранения в БД: {e}")
            return 0, elapsed_ms

    def run_e2e_benchmark(
        self,
        dataset: List[Dict[str, Any]],
        test_user_id: int = 1,
    ) -> Dict[str, float]:
        """Выполнить бенчмарк E2E (End-to-End).

        Измеряет полное время ответа от отправки вопроса до получения ответа.

        Args:
            dataset: Список вопросов
            test_user_id: ID тестового пользователя

        Returns:
            Словарь с метриками TTA
        """
        logger.info(f"Запуск E2E бенчмарка с {len(dataset)} вопросами")

        self.collector.clear()

        tta_e2e_values = []
        cache_hits = 0
        cache_total = 0

        for item in dataset:
            question = item["question"]
            ground_truth = item.get("ground_truth_answer", "")
            final_answer = ""
            final_url = None

            e2e_start = time.perf_counter()

            with TTATimingContext(self.collector, "TTA_DB_Context") as timing1:
                dialog_context, context_time = self._measure_db_context_extraction(
                    test_user_id
                )

            with TTATimingContext(self.collector, "TTA_Cache_Search") as timing2:
                cache_result, cache_hit, cache_time = self._measure_cache_search(
                    question
                )

            cache_total += 1
            if cache_hit:
                cache_hits += 1

                with TTATimingContext(self.collector, "TTA_Judge_Cache") as timing3:
                    cached_answer, cached_url = cache_result
                    judge_result, judge_time = self._measure_judge_assessment(
                        dialog_context, question, cached_answer, "", generation=False
                    )

                if judge_result:
                    final_answer = cached_answer
                    final_url = cached_url
                else:
                    with TTATimingContext(
                        self.collector, "TTA_Chunk_Search"
                    ) as timing4:
                        chunk, chunk_time = self._measure_chunk_search(question)

                    if chunk:
                        with TTATimingContext(
                            self.collector, "TTA_LLM_Generation"
                        ) as timing5:
                            final_answer, llm_time = self._measure_llm_generation(
                                dialog_context, chunk.text, question
                            )

                        with TTATimingContext(
                            self.collector, "TTA_Judge_Generation"
                        ) as timing6:
                            judge_result_gen, judge_time_gen = (
                                self._measure_judge_assessment(
                                    dialog_context,
                                    question,
                                    final_answer,
                                    chunk.text,
                                    generation=True,
                                )
                            )

                            if not judge_result_gen:
                                final_answer = ""
                    else:
                        final_answer = ""
                        final_url = None
            else:
                with TTATimingContext(self.collector, "TTA_Chunk_Search") as timing4:
                    chunk, chunk_time = self._measure_chunk_search(question)

                if chunk:
                    with TTATimingContext(
                        self.collector, "TTA_LLM_Generation"
                    ) as timing5:
                        final_answer, llm_time = self._measure_llm_generation(
                            dialog_context, chunk.text, question
                        )
                    final_url = chunk.confluence_url

                    with TTATimingContext(
                        self.collector, "TTA_Judge_Generation"
                    ) as timing6:
                        judge_result, judge_time = self._measure_judge_assessment(
                            dialog_context,
                            question,
                            final_answer,
                            chunk.text,
                            generation=True,
                        )

                        if not judge_result:
                            final_answer = ""
                else:
                    final_answer = ""
                    final_url = None

            with TTATimingContext(self.collector, "TTA_DB_Save") as timing7:
                qa_id, save_time = self._measure_db_save(
                    question, final_answer, final_url, test_user_id
                )

            e2e_elapsed_ms = (time.perf_counter() - e2e_start) * 1000
            tta_e2e_values.append(e2e_elapsed_ms)
            self.collector.record("TTA_E2E", e2e_elapsed_ms)

            logger.debug(
                f"Вопрос: {question[:50]}... | "
                f"E2E: {e2e_elapsed_ms:.0f}ms | "
                f"Cache hit: {cache_hit}"
            )

        metrics = self.collector.get_all_metrics()

        cache_hit_rate = cache_hits / cache_total if cache_total > 0 else 0.0

        e2e_stats = {
            "TTA_E2E_mean": np.mean(tta_e2e_values) if tta_e2e_values else 0.0,
            "TTA_E2E_std": np.std(tta_e2e_values) if tta_e2e_values else 0.0,
            "TTA_E2E_min": np.min(tta_e2e_values) if tta_e2e_values else 0.0,
            "TTA_E2E_max": np.max(tta_e2e_values) if tta_e2e_values else 0.0,
            "TTA_E2E_P50": np.percentile(tta_e2e_values, 50) if tta_e2e_values else 0.0,
            "TTA_E2E_P90": np.percentile(tta_e2e_values, 90) if tta_e2e_values else 0.0,
            "TTA_E2E_P95": np.percentile(tta_e2e_values, 95) if tta_e2e_values else 0.0,
            "TTA_E2E_P99": np.percentile(tta_e2e_values, 99) if tta_e2e_values else 0.0,
        }

        metrics.update(e2e_stats)
        metrics["Cache_Hit_Rate"] = cache_hit_rate

        logger.info(
            f"E2E бенчмарк завершен. "
            f"Среднее TTA: {metrics['TTA_E2E_mean']:.0f}ms, "
            f"P95: {metrics['TTA_E2E_P95']:.0f}ms, "
            f"Cache hit rate: {cache_hit_rate:.2%}"
        )

        return metrics

    def run_component_benchmark(
        self,
        dataset: List[Dict[str, Any]],
        test_user_id: int = 1,
    ) -> Dict[str, float]:
        """Выполнить компонентный бенчмарк.

        Измеряет время выполнения каждого компонента отдельно.

        Args:
            dataset: Список вопросов
            test_user_id: ID тестового пользователя

        Returns:
            Словарь с метриками компонентов
        """
        logger.info(f"Запуск компонентного бенчмарка с {len(dataset)} вопросами")

        self.collector.clear()

        cache_hits = 0
        cache_total = 0

        for item in dataset:
            question = item["question"]

            dialog_context, context_time = self._measure_db_context_extraction(
                test_user_id
            )
            self.collector.record("TTA_DB_Context", context_time)

            cache_result, cache_hit, cache_time = self._measure_cache_search(question)
            self.collector.record("TTA_Cache_Search", cache_time)
            cache_total += 1
            if cache_hit:
                cache_hits += 1

            chunk, chunk_time = self._measure_chunk_search(question)
            self.collector.record("TTA_Chunk_Search", chunk_time)

            if chunk:
                answer, llm_time = self._measure_llm_generation(
                    dialog_context, chunk.text, question
                )
                self.collector.record("TTA_LLM_Generation", llm_time)

                judge_result, judge_time = self._measure_judge_assessment(
                    dialog_context, question, answer, chunk.text, generation=True
                )
                self.collector.record("TTA_Judge_Generation", judge_time)
            else:
                self.collector.record("TTA_LLM_Generation", 0.0)
                self.collector.record("TTA_Judge_Generation", 0.0)

        metrics = self.collector.get_all_metrics()

        metrics["Cache_Hit_Rate"] = cache_hits / cache_total if cache_total > 0 else 0.0

        tta_qa_values = self.collector.get_values("TTA_Cache_Search")
        tta_qa_values.extend(self.collector.get_values("TTA_Chunk_Search"))
        tta_qa_values.extend(self.collector.get_values("TTA_LLM_Generation"))

        if tta_qa_values:
            metrics["TTA_QA_mean"] = float(np.mean(tta_qa_values))
            metrics["TTA_QA_P50"] = float(np.percentile(tta_qa_values, 50))
            metrics["TTA_QA_P95"] = float(np.percentile(tta_qa_values, 95))
        else:
            metrics["TTA_QA_mean"] = 0.0
            metrics["TTA_QA_P50"] = 0.0
            metrics["TTA_QA_P95"] = 0.0

        logger.info(
            f"Компонентный бенчмарк завершен. "
            f"Cache hit rate: {metrics['Cache_Hit_Rate']:.2%}"
        )

        return metrics

    def get_collector(self) -> TTAMetricsCollector:
        """Получить коллектор метрик.

        Returns:
            Коллектор метрик
        """
        return self.collector
