"""Пересчёт эмбеддингов чанков в БД на модель deepvk/USER-bge-m3.

Скрипт подключается к PostgreSQL, читает все чанки с текстом,
вычисляет эмбеддинги моделью deepvk/USER-bge-m3 и обновляет
колонку embedding в таблице chunk.

Использование:
    cd Submodules/voproshalych
    uv run python benchmarks/reembed_v1_chunks.py
"""

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv(dotenv_path=".env.docker")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

NEW_MODEL = "deepvk/USER-bge-m3"
BATCH_SIZE = 32


def main():
    """Пересчитать эмбеддинги всех чанков на deepvk/USER-bge-m3."""
    from sentence_transformers import SentenceTransformer

    from qa.config import Config
    from qa.database import Chunk
    from sqlalchemy import create_engine, select, text
    from sqlalchemy.orm import Session

    logger.info("Загрузка модели: %s", NEW_MODEL)
    model = SentenceTransformer(NEW_MODEL, device="cpu")
    dim = model.get_sentence_embedding_dimension()
    logger.info("Модель загружена, размерность: %d", dim)

    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)

    with Session(engine) as session:
        chunk_rows = session.execute(
            select(Chunk.id, Chunk.text).order_by(Chunk.id)
        ).all()

    total = len(chunk_rows)
    logger.info("Найдено чанков: %d", total)

    if total == 0:
        logger.error("Нет чанков в БД")
        return

    texts = [row[1] for row in chunk_rows]
    ids = [row[0] for row in chunk_rows]

    logger.info(
        "Вычисление эмбеддингов (%d текстов, batch=%d)...",
        total,
        BATCH_SIZE,
    )
    t0 = time.perf_counter()
    embeddings = model.encode(
        texts,
        batch_size=BATCH_SIZE,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    elapsed = time.perf_counter() - t0
    logger.info("Эмбеддинги вычислены за %.1fs", elapsed)

    logger.info("Обновление БД...")
    t0 = time.perf_counter()

    with Session(engine) as session:
        for i, chunk_id in enumerate(ids):
            vec_str = "[" + ",".join(str(v) for v in embeddings[i]) + "]"
            session.execute(
                text(
                    "UPDATE chunk SET embedding = CAST(:emb AS vector) "
                    "WHERE id = :cid"
                ),
                {"emb": vec_str, "cid": chunk_id},
            )
        session.commit()

    elapsed = time.perf_counter() - t0
    logger.info("БД обновлена за %.1fs", elapsed)

    with Session(engine) as session:
        count = session.execute(
            text(
                "SELECT count(*) FROM chunk WHERE embedding IS NOT NULL"
            )
        ).scalar()
    logger.info("Готово! Чанков с эмбеддингами: %d/%d", count, total)


if __name__ == "__main__":
    main()
