"""
utils/embeddings.py — AI GRC Audit Suite
==========================================
HuggingFace embedding model setup for RAG (Retrieval-Augmented Generation).

Used exclusively by Module 4 — Gap Assessment Tool.

Why all-mpnet-base-v2:
- Best-in-class free embedding model for semantic similarity
- Runs entirely locally — client policy documents never leave the machine
- 768-dimension vectors — good balance of accuracy vs storage cost
- Widely used in compliance and legal document retrieval tasks

Why embeddings matter for gap assessment:
- Instead of sending 50-page policy docs to Groq (expensive, slow, unreliable)
- We embed the documents, store chunks in ChromaDB
- For each framework control, we retrieve the 5 most relevant chunks
- Groq only sees those 5 chunks + the control definition — much faster and accurate

First-run behaviour:
- The model (~420MB) downloads automatically from HuggingFace Hub on first use
- Cached at ~/.cache/huggingface/hub/ — subsequent runs load instantly
- Internet connection required for first download only

Public functions:
    get_embedding_model()           → SentenceTransformer model instance
    embed_text(text)                → list[float]  (single text embedding)
    embed_batch(texts)              → list[list[float]]  (batch embedding)
    get_embedding_dimension()       → int  (768 for all-mpnet-base-v2)
"""

from typing import Optional

from config.settings import EMBEDDING_MODEL


# =============================================================
# MODULE-LEVEL CACHE
# The model is heavy (~420MB) — load once, reuse everywhere.
# _model starts as None and is set on first call to get_embedding_model().
# =============================================================

_model = None   # type: Optional[object]


def get_embedding_model():
    """
    Load and return the HuggingFace all-mpnet-base-v2 embedding model.

    Uses a module-level cache so the model is only loaded once per
    application session. Loading takes ~3-5 seconds on first call
    (after the initial download), then returns instantly on all
    subsequent calls.

    First-run: downloads ~420MB from HuggingFace Hub.
    Cached at: ~/.cache/huggingface/hub/  (automatic)

    Called by:
        utils/vectorstore.py → store_documents()  (to embed document chunks)
        utils/vectorstore.py → query()             (to embed the search query)

    Returns:
        SentenceTransformer model instance ready to call .encode() on

    Raises:
        RuntimeError if the model cannot be loaded (e.g. no internet on first run)
    """
    global _model

    # Return cached instance if already loaded — avoids reloading 420MB model
    if _model is not None:
        return _model

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise RuntimeError(
            "sentence-transformers is not installed.\n"
            "Run: pip install sentence-transformers"
        )

    try:
        # Load the model — downloads on first run, cached locally after
        # device=None lets sentence-transformers auto-detect CPU vs GPU
        _model = SentenceTransformer(EMBEDDING_MODEL)
        return _model

    except Exception as e:
        error_msg = str(e)

        # Network error on first download — give a specific, helpful message
        if "403" in error_msg or "connection" in error_msg.lower() or "network" in error_msg.lower():
            raise RuntimeError(
                f"Could not download the embedding model '{EMBEDDING_MODEL}'.\n"
                "This model needs to download ~420MB from HuggingFace on first use.\n\n"
                "If you are on a restricted network:\n"
                "  1. Run the app on a machine with internet access first to cache the model\n"
                "  2. The model caches at ~/.cache/huggingface/hub/ — copy that folder across\n\n"
                f"Original error: {e}"
            ) from e

        # Any other error
        raise RuntimeError(
            f"Failed to load embedding model '{EMBEDDING_MODEL}': {e}"
        ) from e


def embed_text(text: str) -> list:
    """
    Generate an embedding vector for a single text string.

    Used to embed individual framework control descriptions
    when querying ChromaDB for relevant document chunks.

    Args:
        text : Any string — typically a framework control description
               or a search query

    Returns:
        List of floats representing the 768-dimensional embedding vector.
        e.g. [0.023, -0.451, 0.118, ...]
    """
    model = get_embedding_model()

    # encode() returns a numpy array — convert to plain Python list
    # so it can be stored in ChromaDB without numpy dependency issues
    embedding = model.encode(text, convert_to_numpy=True)
    return embedding.tolist()


def embed_batch(texts: list) -> list:
    """
    Generate embedding vectors for a list of text strings in one batch.

    Batch encoding is significantly faster than calling embed_text()
    in a loop — the model processes multiple texts in parallel on GPU
    or in optimised batches on CPU.

    Used to embed all document chunks at once when a user uploads
    policy documents in Module 4.

    Args:
        texts : List of strings to embed. Can be any length.

    Returns:
        List of embedding vectors — one per input text.
        e.g. [[0.023, ...], [-0.451, ...], ...]
    """
    if not texts:
        return []

    model = get_embedding_model()

    # show_progress_bar=False keeps output clean in Streamlit context
    # batch_size=32 is safe on CPU — increase to 64+ if GPU available
    embeddings = model.encode(
        texts,
        convert_to_numpy=True,
        show_progress_bar=False,
        batch_size=32,
    )

    # Convert numpy array of arrays to Python list of lists
    return [emb.tolist() for emb in embeddings]


def get_embedding_dimension() -> int:
    """
    Return the dimensionality of vectors produced by the embedding model.

    all-mpnet-base-v2 produces 768-dimensional vectors.
    Used by ChromaDB collection setup to confirm configuration.

    Returns:
        int — 768 for all-mpnet-base-v2
    """
    model = get_embedding_model()
    # Encode a dummy string and measure the output vector length
    dummy = model.encode("dimension check", convert_to_numpy=True)
    return len(dummy)
