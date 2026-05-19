from __future__ import annotations

import shutil
import re
from dataclasses import dataclass
from pathlib import Path

from src.config import Settings, load_settings
from src.logger import get_logger


SUPPORTED_DOCUMENT_SUFFIXES = {
    ".txt",
    ".md",
    ".markdown",
    ".py",
    ".json",
    ".csv",
    ".yaml",
    ".yml",
    ".pdf",
}


@dataclass
class RAGMemory:
    settings: Settings | None = None

    def __post_init__(self) -> None:
        self.settings = self.settings or load_settings()
        self._vector_store = None
        self._vector_store_unavailable_reason: str | None = None
        self._logger = get_logger(__name__)

    def list_document_paths(self) -> list[Path]:
        documents_dir = self.settings.documents_dir
        if not documents_dir.exists():
            return []

        return sorted(
            path
            for path in documents_dir.rglob("*")
            if path.is_file()
            and path.suffix.lower() in SUPPORTED_DOCUMENT_SUFFIXES
            and not path.name.startswith(".")
        )

    def build_or_update_index(self) -> int:
        if not self.settings.rag_enabled:
            self._logger.info("RAG is disabled")
            return 0

        documents = self._load_documents()
        if not documents:
            self._logger.info("No local documents found for RAG indexing")
            return 0

        try:
            from langchain_chroma import Chroma
            from langchain_openai import OpenAIEmbeddings
            from langchain_text_splitters import RecursiveCharacterTextSplitter

            if self.settings.vector_store_dir.exists():
                shutil.rmtree(self.settings.vector_store_dir)
            self.settings.vector_store_dir.mkdir(parents=True, exist_ok=True)

            splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.settings.rag_chunk_size,
                chunk_overlap=self.settings.rag_chunk_overlap,
                add_start_index=True,
            )
            chunks = splitter.split_documents(documents)

            embeddings = OpenAIEmbeddings(model=self.settings.embedding_model)
            self._vector_store = Chroma.from_documents(
                documents=chunks,
                embedding=embeddings,
                collection_name=self.settings.chroma_collection,
                persist_directory=str(self.settings.vector_store_dir),
            )

            self._logger.info("Indexed %s document chunks", len(chunks))
            return len(chunks)

        except ImportError as error:
            self._mark_vector_store_unavailable(f"RAG dependencies are not installed: {error}")
            return 0
        except Exception as error:
            self._mark_vector_store_unavailable(f"RAG indexing failed: {error}")
            return 0

    def ensure_index(self) -> None:
        if not self.settings.rag_enabled:
            return

        has_existing_index = (self.settings.vector_store_dir / "chroma.sqlite3").exists()
        if has_existing_index:
            return

        if self.list_document_paths():
            self.build_or_update_index()

    def retrieve_context(self, query: str) -> str:
        if not self.settings.rag_enabled or not query.strip():
            return ""

        document_context = self._retrieve_named_document_context(query)
        if document_context:
            return document_context

        if self._vector_store_unavailable_reason:
            return self._retrieve_context_with_keyword_search(query)

        try:
            vector_store = self._get_vector_store()
            documents = vector_store.similarity_search(
                query,
                k=self.settings.rag_top_k,
            )

            if not documents:
                return ""

            formatted_fragments = []
            for index, document in enumerate(documents, start=1):
                source = document.metadata.get("source", "unknown")
                content = " ".join(document.page_content.split())
                formatted_fragments.append(f"[{index}] {source}: {content}")

            return "\n".join(formatted_fragments)

        except Exception as error:
            self._mark_vector_store_unavailable(f"RAG retrieval failed: {error}")
            return self._retrieve_context_with_keyword_search(query)

    def status(self) -> str:
        documents_count = len(self.list_document_paths())
        index_exists = (self.settings.vector_store_dir / "chroma.sqlite3").exists()
        state = "enabled" if self.settings.rag_enabled else "disabled"
        index_state = "ready" if index_exists else "not built"
        if self._vector_store_unavailable_reason:
            index_state = "keyword fallback"
        return (
            f"RAG: {state}; documents: {documents_count}; "
            f"index: {index_state}; directory: {self.settings.documents_dir}"
        )

    def _retrieve_named_document_context(self, query: str) -> str:
        requested_name = self._extract_requested_document_name(query)
        if not requested_name:
            return ""

        path = self._find_document_by_name(requested_name)
        if path is None:
            return ""

        text = self._read_document_text(path)
        if not text:
            return ""

        relative_source = str(path.relative_to(self.settings.documents_dir))
        clipped = " ".join(text.split())[:4000]
        return (
            f"[1] {relative_source}: {clipped}\n\n"
            f"Zrodlo: {relative_source}\n"
            "Instrukcja RAG: uzytkownik prosi o przeczytanie tego dokumentu. "
            "Jesli pyta o decyzje, stresc decyzje i ustalenia z dokumentu."
        )

    def _find_document_by_name(self, requested_name: str) -> Path | None:
        normalized_requested = self._normalize_doc_name(requested_name)
        for path in self.list_document_paths():
            candidates = {
                self._normalize_doc_name(path.name),
                self._normalize_doc_name(path.stem),
                self._normalize_doc_name(str(path.relative_to(self.settings.documents_dir))),
            }
            if normalized_requested in candidates:
                return path
            if any(normalized_requested and normalized_requested in candidate for candidate in candidates):
                return path
        return None

    def _read_document_text(self, path: Path) -> str:
        if path.suffix.lower() == ".pdf":
            try:
                from langchain_community.document_loaders import PyPDFLoader

                pages = PyPDFLoader(str(path)).load()
                return "\n".join(page.page_content for page in pages)
            except Exception as error:
                self._logger.warning("Cannot read PDF %s: %s", path, error)
                return ""

        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return ""

    def _get_vector_store(self):
        if self._vector_store is not None:
            return self._vector_store

        if self._vector_store_unavailable_reason:
            raise RuntimeError(self._vector_store_unavailable_reason)

        from langchain_chroma import Chroma
        from langchain_openai import OpenAIEmbeddings

        embeddings = OpenAIEmbeddings(model=self.settings.embedding_model)
        self._vector_store = Chroma(
            collection_name=self.settings.chroma_collection,
            embedding_function=embeddings,
            persist_directory=str(self.settings.vector_store_dir),
        )
        return self._vector_store

    def _mark_vector_store_unavailable(self, reason: str) -> None:
        if self._vector_store_unavailable_reason is None:
            self._logger.debug("%s. Using keyword RAG fallback.", reason)
        self._vector_store_unavailable_reason = reason
        self._vector_store = None

    def _retrieve_context_with_keyword_search(self, query: str) -> str:
        query_terms = self._tokenize(query)
        if not query_terms:
            return ""

        scored_fragments: list[tuple[int, str, str]] = []
        for path in self.list_document_paths():
            if path.suffix.lower() == ".pdf":
                continue

            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            for fragment in self._split_plain_text(text):
                fragment_terms = set(self._tokenize(fragment))
                score = len(query_terms & fragment_terms)
                if score > 0:
                    source = str(path.relative_to(self.settings.documents_dir))
                    scored_fragments.append((score, source, fragment))

        scored_fragments.sort(key=lambda item: item[0], reverse=True)
        formatted_fragments = []
        for index, (_score, source, fragment) in enumerate(
            scored_fragments[: self.settings.rag_top_k],
            start=1,
        ):
            content = " ".join(fragment.split())
            formatted_fragments.append(f"[{index}] {source}: {content}")

        return "\n".join(formatted_fragments)

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return set(re.findall(r"\w{3,}", text.lower(), flags=re.UNICODE))

    @staticmethod
    def _extract_requested_document_name(query: str) -> str:
        normalized = " ".join(query.strip().split())
        patterns = [
            r"przeczytaj dokument\s+(.+?)(?:\s+i\s+|$)",
            r"stresc dokument\s+(.+?)(?:\s+i\s+|$)",
            r"streść dokument\s+(.+?)(?:\s+i\s+|$)",
            r"otworz dokument\s+(.+?)(?:\s+i\s+|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, normalized, flags=re.IGNORECASE)
            if match:
                return match.group(1).strip(" .,:;\"'")
        return ""

    @staticmethod
    def _normalize_doc_name(name: str) -> str:
        translation = str.maketrans("ąćęłńóśźż", "acelnoszz")
        name = name.lower().translate(translation)
        name = re.sub(r"[^a-z0-9. _-]+", " ", name)
        return " ".join(name.split())

    def _split_plain_text(self, text: str) -> list[str]:
        chunk_size = max(200, self.settings.rag_chunk_size)
        overlap = min(self.settings.rag_chunk_overlap, chunk_size // 2)
        fragments = []
        start = 0

        while start < len(text):
            end = min(start + chunk_size, len(text))
            fragments.append(text[start:end])
            if end == len(text):
                break
            start = max(end - overlap, start + 1)

        return fragments

    def _load_documents(self):
        try:
            from langchain_community.document_loaders import PyPDFLoader, TextLoader
        except ImportError as error:
            self._logger.warning("Document loaders are not installed: %s", error)
            return []

        loaded_documents = []
        for path in self.list_document_paths():
            try:
                if path.suffix.lower() == ".pdf":
                    documents = PyPDFLoader(str(path)).load()
                else:
                    documents = TextLoader(str(path), encoding="utf-8").load()

                for document in documents:
                    document.metadata["source"] = str(path.relative_to(self.settings.documents_dir))
                loaded_documents.extend(documents)

            except Exception as error:
                self._logger.warning("Cannot load document %s: %s", path, error)

        return loaded_documents
