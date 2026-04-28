"""Парсер для пространства Study на Confluence."""

import logging
from typing import Generator

from atlassian import Confluence
from bs4 import BeautifulSoup
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from config import Config
from database import Chunk


class ConfluenceStudyParser:
    """Парсер для извлечения документов из пространства Study на Confluence."""

    def __init__(self, confluence: Confluence | None = None):
        """Инициализирует парсер.

        Args:
            confluence: экземпляр Confluence API (создаётся автоматически если не передан)
        """
        self.confluence = confluence or Confluence(
            url=Config.CONFLUENCE_HOST, token=Config.CONFLUENCE_TOKEN
        )

    def get_page_content(
        self, page_id: str
    ) -> Generator[tuple[str, str], None, None]:
        """Возвращает содержимое страницы на Confluence.

        Args:
            page_id: ID страницы

        Yields:
            tuple[str, str]: содержимое страницы, ссылка на страницу
        """
        page = self.confluence.get_page_by_id(page_id, expand="space,body.export_view")
        page_link = page["_links"]["base"] + page["_links"]["webui"]
        page_body = page["body"]["export_view"]["value"]
        page_download = (
            page["_links"]["base"] + page["_links"]["download"]
            if "download" in page["_links"].keys()
            else ""
        )

        try:
            if len(page_body) > 50:
                soup = BeautifulSoup(page_body, "html.parser")
                page_body_text = soup.get_text(separator=" ")
                page_content = page_body_text.replace(" \n ", "")
            elif ".pdf" in page_download.lower():
                loader = PyPDFLoader(page_download.split("?")[0])
                page_content = " ".join(
                    [p.page_content for p in loader.load_and_split()]
                )
            else:
                return
            yield page_content, page_link
        except Exception as e:
            logging.error(f"Error processing page {page_id}: {e}")

    def get_all_pages(self, space: str = "study") -> Generator[str, None, None]:
        """Получает все страницы в пространстве.

        Args:
            space: код пространства (по умолчанию "study")

        Yields:
            str: ID страницы
        """
        spaces = f"space = {space}"
        count_start = 0
        limit = 100

        while True:
            query = f"{spaces} order by id"
            pages = self.confluence.cql(query, start=count_start, limit=limit)["results"]
            if len(pages) == 0:
                break
            for page in pages:
                if "content" in page.keys():
                    yield page["content"]["id"]
            count_start += limit

    def get_leaf_pages(self, space: str = "study") -> Generator[str, None, None]:
        """Получает страницы без вложенных страниц (листья).

        Args:
            space: код пространства

        Yields:
            str: ID страницы
        """
        for page_id in self.get_all_pages(space):
            children = self.confluence.cql(f"parent={page_id}")["results"]
            if len(children) == 0:
                yield page_id

    def parse_and_index(
        self,
        engine: Engine,
        text_splitter,
        encoder_model,
        space: str = "study",
    ) -> None:
        """Парсит страницы из пространства и сохраняет в базу данных.

        Args:
            engine: экземпляр подключения к БД
            text_splitter: разделитель текста на фрагменты
            encoder_model: модель для получения эмбеддингов
            space: код пространства для парсинга
        """
        logging.warning(f"START PARSING STUDY SPACE: {space}")

        for page_id in self.get_leaf_pages(space):
            for content, url in self.get_page_content(page_id):
                documents = [Document(page_content=content, metadata={"page_link": url})]
                all_splits = text_splitter.split_documents(documents)

                for chunk in all_splits:
                    with Session(engine) as session:
                        session.add(
                            Chunk(
                                confluence_url=chunk.metadata["page_link"],
                                text=chunk.page_content,
                                embedding=encoder_model.encode(chunk.page_content),
                            )
                        )
                        session.commit()

        logging.warning(f"STUDY SPACE INDEXED: {space}")


def index_study_space(
    engine: Engine, text_splitter, encoder_model, space: str = "study"
) -> None:
    """Индексирует пространство Study на Confluence.

    Args:
        engine: экземпляр подключения к БД
        text_splitter: разделитель текста на фрагменты
        encoder_model: модель для получения эмбеддингов
        space: код пространства для парсинга
    """
    parser = ConfluenceStudyParser()
    parser.parse_and_index(engine, text_splitter, encoder_model, space)