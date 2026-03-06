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
            expected_scenario = item.get("expected_scenario", "unknown")
            ground_truth = item.get("ground_truth_answer", "")

            e2e_start = time.perf_counter()

            tta_cache_search_ms = 0.0
            tta_judge_cache_ms = 0.0
            tta_chunk_search_ms = 0.0
            tta_llm_generation_ms = 0.0
            tta_judge_generation_ms = 0.0
            tta_db_save_ms = 0.0

            cache_hit_actual = False
            generation_attempted = False
            judge_verdict = False

            real_scenario = "unknown"
            final_answer = ""
            final_url = None

            with TTATimingContext(self.collector, "TTA_DB_Context") as timing1:
                dialog_context, context_time = self._measure_db_context_extraction(
                    test_user_id
                )

            with TTATimingContext(self.collector, "TTA_Cache_Search") as timing2:
                cache_result, cache_hit, cache_time = self._measure_cache_search(
                    question
                )
                tta_cache_search_ms = cache_time

            if cache_hit:
                cache_hit_actual = True

                with TTATimingContext(self.collector, "TTA_Judge_Cache") as timing3:
                    cached_answer, cached_url = cache_result
                    judge_result, judge_time = self._measure_judge_assessment(
                        dialog_context, question, cached_answer, "", generation=False
                    )
                    tta_judge_cache_ms = judge_time

                judge_verdict = judge_result

                if judge_result:
                    final_answer = cached_answer
                    final_url = cached_url
                    real_scenario = "cache_hit"
                else:
                    generation_attempted = True

                    with TTATimingContext(
                        self.collector, "TTA_Chunk_Search"
                    ) as timing4:
                        chunk, chunk_time = self._measure_chunk_search(question)
                        tta_chunk_search_ms = chunk_time

                    if chunk:
                        generation_attempted = True

                        with TTATimingContext(
                            self.collector, "TTA_LLM_Generation"
                        ) as timing5:
                            final_answer, llm_time = self._measure_llm_generation(
                                dialog_context, chunk.text, question
                            )
                            tta_llm_generation_ms = llm_time

                        final_url = chunk.confluence_url

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
                            tta_judge_generation_ms = judge_time_gen
                            judge_verdict = judge_result_gen

                        if not judge_result_gen:
                            final_answer = ""
                            real_scenario = "generation_judge_rejected"
                        else:
                            real_scenario = "generation"
                    else:
                        final_answer = ""
                        final_url = None
                        real_scenario = "generation_chunk_not_found"
            else:
                generation_attempted = True

                with TTATimingContext(self.collector, "TTA_Chunk_Search") as timing4:
                    chunk, chunk_time = self._measure_chunk_search(question)
                    tta_chunk_search_ms = chunk_time

                if chunk:
                    generation_attempted = True

                    with TTATimingContext(
                        self.collector, "TTA_LLM_Generation"
                    ) as timing5:
                        final_answer, llm_time = self._measure_llm_generation(
                            dialog_context, chunk.text, question
                        )
                        tta_llm_generation_ms = llm_time

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
                        tta_judge_generation_ms = judge_time
                        judge_verdict = judge_result

                    if not judge_result:
                        final_answer = ""
                        real_scenario = "generation_judge_rejected"
                    elif "not found" in final_answer.lower() or len(final_answer) == 0:
                        real_scenario = "template"
                    else:
                        real_scenario = "generation"
                else:
                    real_scenario = "chunk_not_found"

            with TTATimingContext(self.collector, "TTA_DB_Save") as timing7:
                qa_id, save_time = self._measure_db_save(
                    question, final_answer, final_url, test_user_id
                )
                tta_db_save_ms = save_time

            e2e_elapsed_ms = (time.perf_counter() - e2e_start) * 1000
            tta_e2e_values.append(e2e_elapsed_ms)
            self.collector.record("TTA_E2E", e2e_elapsed_ms)

            item.update(
                {
                    "real_scenario": real_scenario,
                    "real_answer": final_answer,
                    "real_confluence_url": final_url,
                    "real_judge_verdict": judge_verdict,
                    "tta_e2e_ms": e2e_elapsed_ms,
                    "tta_cache_search_ms": tta_cache_search_ms,
                    "tta_judge_cache_ms": tta_judge_cache_ms,
                    "tta_chunk_search_ms": tta_chunk_search_ms,
                    "tta_llm_generation_ms": tta_llm_generation_ms,
                    "tta_judge_generation_ms": tta_judge_generation_ms,
                    "tta_db_save_ms": tta_db_save_ms,
                    "cache_hit_actual": cache_hit_actual,
                    "generation_attempted": generation_attempted,
                }
            )

            logger.debug(
                f"Вопрос: {question[:50]}... | "
                f"E2E: {e2e_elapsed_ms:.0f}ms | "
                f"Cache hit: {cache_hit}"
            )

        metrics = self.collector.get_all_metrics()

        metrics_by_scenario = {
            "cache_hit": {},
            "generation": {},
            "generation_judge_rejected": {},
            "generation_chunk_not_found": {},
            "template": {},
            "chunk_not_found": {},
            "unknown": {},
        }

        tta_e2e_by_scenario = {
            "cache_hit": [],
            "generation": [],
            "generation_judge_rejected": [],
            "generation_chunk_not_found": [],
            "template": [],
            "chunk_not_found": [],
            "unknown": [],
        }

        for item in dataset:
            scenario = item.get("real_scenario", "unknown")
            tta_e2e = item.get("tta_e2e_ms", 0.0)
            tta_e2e_by_scenario[scenario].append(tta_e2e)

        for scenario in metrics_by_scenario:
            tta_values = tta_e2e_by_scenario[scenario]
            if tta_values:
                metrics_by_scenario[scenario][f"TTA_E2E_mean"] = float(
                    np.mean(tta_values)
                )
                metrics_by_scenario[scenario][f"TTA_E2E_P50"] = float(
                    np.percentile(tta_values, 50)
                )
                metrics_by_scenario[scenario][f"TTA_E2E_P95"] = float(
                    np.percentile(tta_values, 95)
                )
                metrics_by_scenario[scenario][f"TTA_E2E_P99"] = float(
                    np.percentile(tta_values, 99)
                )
                metrics_by_scenario[scenario]["count"] = len(tta_values)

        metrics.update(metrics_by_scenario)

        total_questions = len(dataset)
        metrics["total_questions"] = total_questions

        logger.info(f"E2E бенчмарк завершен. Всего вопросов: {total_questions}")

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
