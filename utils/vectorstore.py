"""
utils/vectorstore.py — AI GRC Audit Suite
==========================================
All ChromaDB vector database operations.

No module should ever call ChromaDB directly — always go through here.

Used by Module 4 (Gap Assessment Tool) to:
1. Load client-uploaded policy documents (PDF, DOCX, TXT)
2. Split them into overlapping chunks
3. Embed each chunk using HuggingFace all-mpnet-base-v2
4. Store chunks + embeddings in ChromaDB under a named collection
5. For each framework control, retrieve the most relevant chunks
6. Pass those chunks to Groq for gap verdict

Public functions:
    load_and_chunk_files(file_paths)           → list[dict]
    store_documents(chunks, collection_name)   → int
    query(collection_name, query_text, k)      → list[str]
    collection_exists(collection_name)         → bool
    delete_collection(collection_name)         → None
    get_collection_info(collection_name)       → dict
    make_collection_name(company, framework)   → str
"""

import os
import re
import uuid
from pathlib import Path

import chromadb

from config.settings import (
    CHROMA_DB_PATH,
    CHROMA_COLLECTION_PREFIX,
    CHROMA_RETRIEVAL_K,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
)
from utils.embeddings import embed_text, embed_batch


# =============================================================
# CHROMADB CLIENT
# =============================================================

def _get_chroma_client():
    """
    Create and return a ChromaDB persistent client.
    Creates the storage directory if it does not exist.
    """
    db_path = os.path.abspath(CHROMA_DB_PATH)
    os.makedirs(db_path, exist_ok=True)
    return chromadb.PersistentClient(path=db_path)


# =============================================================
# DOCUMENT LOADING AND CHUNKING
# =============================================================

def _load_file_text(file_path):
    """
    Load the text content of a single file.
    Supports PDF, DOCX, and TXT files.
    """
    path = Path(file_path)
    ext = path.suffix.lower()

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if ext == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n\n".join(pages)
        except ImportError:
            raise RuntimeError("pypdf is required to read PDF files. Run: pip install pypdf")

    elif ext in (".docx", ".doc"):
        try:
            import docx2txt
            return docx2txt.process(str(path))
        except ImportError:
            raise RuntimeError("docx2txt is required to read DOCX files. Run: pip install docx2txt")

    elif ext == ".txt":
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    else:
        raise ValueError(
            f"Unsupported file type: {ext}. "
            "Supported formats: PDF (.pdf), Word (.docx), Text (.txt)"
        )


def _chunk_text(text, source_name="document"):
    """
    Split a long text string into overlapping chunks for embedding.

    Args:
        text        : Full document text
        source_name : Filename — stored as chunk metadata

    Returns:
        List of dicts: {text, source, chunk_id}
    """
    # Clean up whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    text = text.strip()

    if not text:
        return []

    chunks = []
    start = 0
    chunk_id = 0

    while start < len(text):
        end = start + CHUNK_SIZE

        if end < len(text):
            # Prefer breaking at paragraph boundary
            para_break = text.rfind("\n\n", start, end)
            if para_break > start + CHUNK_SIZE // 2:
                end = para_break
            else:
                sentence_break = text.rfind(". ", start, end)
                if sentence_break > start + CHUNK_SIZE // 2:
                    end = sentence_break + 1

        chunk_text = text[start:end].strip()

        if chunk_text:
            chunks.append({
                "text":     chunk_text,
                "source":   source_name,
                "chunk_id": chunk_id,
            })
            chunk_id += 1

        # Move forward with overlap
        next_start = end - CHUNK_OVERLAP
        if next_start <= start or next_start >= len(text):
            break
        start = next_start

    return chunks


def load_and_chunk_files(file_paths):
    """
    Load multiple files and split them all into chunks.
    Errors per file are collected rather than crashing.

    Returns:
        List of chunk dicts from all successfully loaded files.
    """
    all_chunks = []
    errors = []

    for file_path in file_paths:
        file_name = Path(str(file_path)).name

        try:
            raw_text = _load_file_text(str(file_path))

            if not raw_text.strip():
                errors.append(f"{file_name}: file appears empty or has no extractable text")
                continue

            file_chunks = _chunk_text(raw_text, source_name=file_name)

            if not file_chunks:
                errors.append(f"{file_name}: no text chunks could be extracted")
                continue

            all_chunks.extend(file_chunks)

        except FileNotFoundError:
            errors.append(f"{file_name}: file not found")
        except ValueError as e:
            errors.append(f"{file_name}: {e}")
        except Exception as e:
            errors.append(f"{file_name}: unexpected error — {e}")

    if errors:
        all_chunks.append({
            "text":     "\n".join(errors),
            "source":   "__ERRORS__",
            "chunk_id": -1,
        })

    return all_chunks


# =============================================================
# CHROMADB STORAGE OPERATIONS
# =============================================================

def store_documents(chunks, collection_name):
    """
    Embed and store document chunks in ChromaDB.

    Deletes any existing collection with the same name first,
    then creates a fresh one and stores all valid chunks.

    Args:
        chunks          : Output of load_and_chunk_files()
        collection_name : ChromaDB collection name

    Returns:
        Number of chunks stored.
    """
    # Filter out error marker chunks — only store real content
    valid_chunks = [c for c in chunks if c.get("source") != "__ERRORS__"]

    if not valid_chunks:
        raise ValueError(
            "No valid document chunks to store. "
            "Check that your uploaded files contain extractable text."
        )

    client = _get_chroma_client()

    # Delete existing collection so re-uploads start clean
    try:
        client.delete_collection(name=collection_name)
    except Exception:
        pass  # Collection did not exist — that is fine

    # Create fresh collection with cosine similarity space
    collection = client.create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )

    # Extract text strings for embedding
    texts = [chunk["text"] for chunk in valid_chunks]

    # Generate embeddings for all chunks in one batch
    embeddings = embed_batch(texts)

    # Generate unique IDs for each chunk
    ids = [str(uuid.uuid4()) for _ in valid_chunks]

    # Build metadata list — one dict per chunk
    metadatas = [
        {"source": c["source"], "chunk_id": c["chunk_id"]}
        for c in valid_chunks
    ]

    # Store everything in ChromaDB
    collection.add(
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids,
    )

    return len(valid_chunks)


# =============================================================
# CHROMADB QUERY OPERATIONS
# =============================================================

def query(collection_name, query_text, n_results=CHROMA_RETRIEVAL_K):
    """
    Retrieve the most relevant document chunks for a query string.

    Args:
        collection_name : ChromaDB collection to search
        query_text      : Search query — typically a control description
        n_results       : Number of chunks to retrieve (default 5)

    Returns:
        List of text strings ordered by relevance.
        Empty list if collection does not exist or has no content.
    """
    client = _get_chroma_client()

    try:
        collection = client.get_collection(name=collection_name)
    except Exception:
        return []

    # Count how many chunks are stored
    stored_count = collection.count()
    if stored_count == 0:
        return []

    # Clamp request to available chunks — ChromaDB errors if you ask for more
    # than exist in the collection
    fetch_count = min(n_results, stored_count)

    # Embed the query text to search by semantic similarity
    query_embedding = embed_text(query_text)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=fetch_count,
        include=["documents", "metadatas", "distances"],
    )

    # results["documents"] is list-of-lists (one per query) — take index 0
    return results.get("documents", [[]])[0]


# =============================================================
# UTILITY FUNCTIONS
# =============================================================

def collection_exists(collection_name):
    """Return True if a non-empty collection with this name exists."""
    client = _get_chroma_client()
    try:
        col = client.get_collection(name=collection_name)
        return col.count() > 0
    except Exception:
        return False


def delete_collection(collection_name):
    """Delete a ChromaDB collection. No-op if it does not exist."""
    client = _get_chroma_client()
    try:
        client.delete_collection(name=collection_name)
    except Exception:
        pass


def get_collection_info(collection_name):
    """Return metadata about a collection: name, chunk_count, exists."""
    client = _get_chroma_client()
    try:
        col = client.get_collection(name=collection_name)
        return {"name": collection_name, "chunk_count": col.count(), "exists": True}
    except Exception:
        return {"name": collection_name, "chunk_count": 0, "exists": False}


def make_collection_name(company_name, framework_id):
    """
    Generate a safe ChromaDB collection name.
    ChromaDB requires: 3-63 chars, alphanumeric + underscores/hyphens,
    no leading/trailing hyphens.

    Args:
        company_name  : e.g. "Al Rajhi Technologies"
        framework_id  : e.g. "NCA_ECC"

    Returns:
        Safe collection name e.g. "grc_gap_al_rajhi_technologies_nca-ecc"
    """
    clean_company = re.sub(r"[^a-zA-Z0-9 ]", "", company_name)
    clean_company = clean_company.strip().replace(" ", "_").lower()[:30]
    clean_fw = framework_id.lower().replace("_", "-")[:20]

    name = f"{CHROMA_COLLECTION_PREFIX}{clean_company}_{clean_fw}"

    if len(name) < 3:
        name = f"{CHROMA_COLLECTION_PREFIX}default"

    return name
