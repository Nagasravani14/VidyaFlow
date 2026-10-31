"""
VidyaFlow - ChromaDB Vector Store Service
Handles persistent local vector storage using ChromaDB and local HuggingFace embeddings
(sentence-transformers/all-MiniLM-L6-v2) for $0 cost and zero API rate limits.
"""

import os
import re
from typing import Any, Dict, List, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils import embedding_functions

# Default collection name and embedding model
COLLECTION_NAME = "vidyaflow_textbooks"
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def normalize_board(board: str) -> str:
    """Normalize board identifiers into canonical 'TS' or 'ICSE'."""
    b = (board or "").strip().upper()
    if "TS" in b or "TELANGANA" in b or "SCERT" in b:
        return "TS"
    if "ICSE" in b or "CISCE" in b:
        return "ICSE"
    return b


def normalize_subject_candidates(subject: str) -> List[str]:
    """Expands subjects to handle aliases (e.g. Physics vs Physical Science)."""
    s = (subject or "").strip().lower()
    if "phys" in s or "chem" in s:
        return ["Physical Science", "Physics", "Chemistry"]
    if "bio" in s:
        return ["Biological Science", "Biology"]
    if "math" in s:
        return ["Mathematics", "Math"]
    if "soc" in s or "hist" in s or "geog" in s or "civ" in s:
        return ["Social Studies", "History", "Geography", "Civics"]
    return [subject.strip()] if subject else []


class ChromaVectorStore:
    """
    Manages persistent ChromaDB vector storage and semantic retrieval
    with strict metadata filtering: {"board": "TS" | "ICSE", "class": int, "subject": str, "chapter": str}
    """

    _instance = None

    def __init__(self, persist_directory: Optional[str] = None):
        if persist_directory is None:
            # Look for environment variable or default to backend/chroma_db
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            persist_directory = os.getenv("CHROMA_DB_DIR", os.path.join(base_dir, "chroma_db"))

        self.persist_directory = os.path.abspath(persist_directory)
        os.makedirs(self.persist_directory, exist_ok=True)

        # Initialize local HuggingFace embedding function (100% free, local)
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL_NAME
        )

        # Initialize persistent Chroma client
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
        )

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self.embedding_function,
            metadata={"description": "VidyaFlow TS and ICSE textbook curriculum chunks"},
        )

    @classmethod
    def get_instance(cls, persist_directory: Optional[str] = None) -> "ChromaVectorStore":
        """Singleton accessor for ChromaVectorStore."""
        if cls._instance is None:
            cls._instance = ChromaVectorStore(persist_directory=persist_directory)
        return cls._instance

    def add_chunks(
        self,
        chunks: List[str],
        metadatas: List[Dict[str, Any]],
        ids: Optional[List[str]] = None,
    ) -> int:
        """
        Stores text chunks into ChromaDB with strict metadata tagging.
        """
        if not chunks:
            return 0

        if ids is None:
            import uuid
            ids = [f"chunk_{uuid.uuid4().hex[:12]}" for _ in range(len(chunks))]

        # Validate and normalize metadata
        clean_metadatas = []
        for meta in metadatas:
            raw_class = meta.get("class_num", meta.get("class", 8))
            try:
                class_int = int(raw_class)
            except (ValueError, TypeError):
                class_int = 8

            clean_meta = {
                "board": normalize_board(str(meta.get("board", "TS"))),
                "class_num": class_int,
                "class": class_int,
                "subject": str(meta.get("subject", "General")).strip(),
                "chapter": str(meta.get("chapter", "General")).strip(),
            }
            # Optional extra fields
            if "source" in meta:
                clean_meta["source"] = str(meta["source"])
            if "page" in meta:
                clean_meta["page"] = int(meta["page"])
            clean_metadatas.append(clean_meta)

        # Upsert into ChromaDB in batches of 200
        batch_size = 200
        total_added = 0
        for i in range(0, len(chunks), batch_size):
            b_chunks = chunks[i : i + batch_size]
            b_metas = clean_metadatas[i : i + batch_size]
            b_ids = ids[i : i + batch_size]

            self.collection.upsert(
                ids=b_ids,
                documents=b_chunks,
                metadatas=b_metas,
            )
            total_added += len(b_chunks)

        return total_added

    def query_curriculum(
        self,
        query: str,
        board: Optional[str] = None,
        class_num: Optional[int] = None,
        subject: Optional[str] = None,
        chapter: Optional[str] = None,
        n_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Performs semantic search with strict and hierarchical metadata filtering.
        If an exact chapter filter yields few results due to naming differences,
        falls back to board/class/subject filtering with semantic similarity.
        """
        if self.collection.count() == 0:
            return []

        conditions = []
        if board:
            conditions.append({"board": {"$eq": normalize_board(board)}})
        if class_num:
            conditions.append({"class_num": {"$eq": int(class_num)}})
        if subject:
            candidates = normalize_subject_candidates(subject)
            if len(candidates) == 1:
                conditions.append({"subject": {"$eq": candidates[0]}})
            elif len(candidates) > 1:
                conditions.append({"subject": {"$in": candidates}})

        # Try query with chapter first if chapter is provided
        where_with_chapter = None
        if chapter and chapter.strip():
            chap_conditions = list(conditions)
            chap_conditions.append({"chapter": {"$eq": chapter.strip()}})
            if len(chap_conditions) == 1:
                where_with_chapter = chap_conditions[0]
            elif len(chap_conditions) > 1:
                where_with_chapter = {"$and": chap_conditions}

        # Build where clause without chapter
        where_without_chapter = None
        if len(conditions) == 1:
            where_without_chapter = conditions[0]
        elif len(conditions) > 1:
            where_without_chapter = {"$and": conditions}

        results = None
        # 1. Attempt with chapter filter
        if where_with_chapter:
            try:
                res = self.collection.query(
                    query_texts=[query],
                    n_results=min(n_results, max(1, self.collection.count())),
                    where=where_with_chapter,
                )
                if res and res["documents"] and len(res["documents"][0]) > 0:
                    results = res
            except Exception:
                results = None

        # 2. If no exact chapter match, query with board, class, subject
        if (not results or not results["documents"] or len(results["documents"][0]) == 0) and where_without_chapter:
            try:
                results = self.collection.query(
                    query_texts=[query + (f" {chapter}" if chapter else "")],
                    n_results=min(n_results, max(1, self.collection.count())),
                    where=where_without_chapter,
                )
            except Exception:
                results = None

        # 3. If still empty, query globally with query text
        if not results or not results["documents"] or len(results["documents"][0]) == 0:
            try:
                results = self.collection.query(
                    query_texts=[query + (f" {subject} {chapter}" if subject or chapter else "")],
                    n_results=min(n_results, max(1, self.collection.count())),
                )
            except Exception:
                return []

        # Format output
        output: List[Dict[str, Any]] = []
        if results and results["documents"]:
            docs = results["documents"][0]
            metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
            dists = results["distances"][0] if results.get("distances") else [0.0] * len(docs)

            for doc, meta, dist in zip(docs, metas, dists):
                c_val = meta.get("class_num", meta.get("class", 8))
                output.append({
                    "text": doc,
                    "metadata": meta,
                    "relevance_distance": float(dist) if dist is not None else 0.0,
                    "chapter": meta.get("chapter", "General"),
                    "subject": meta.get("subject", "General"),
                    "board": meta.get("board", "TS"),
                    "class": c_val,
                    "class_num": c_val,
                })

        return output

    def get_count(self) -> int:
        """Returns total number of chunks stored in vector database."""
        return self.collection.count()
