import os
import re

import weaviate
import weaviate.classes as wvc
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer, models

import doc_security  # digital-signature check (integrity + authenticity)

COLLECTION_NAME = "LegalDocs"

# True  -> every PDF must have a valid '<name>.pdf.sig' signature file, or it is rejected.
# False -> skips the check (e.g. for the web upload flow, until /upload accepts .sig files).
REQUIRE_SIGNATURE = True

# ---------------------------------------------------------------------------
# Embedding model (loaded once, reused for every document)
# ---------------------------------------------------------------------------

print("Loading InLegalBERT embedding model...")
_word_embedding_model = models.Transformer("law-ai/InLegalBERT")
_pooling_model = models.Pooling(_word_embedding_model.get_word_embedding_dimension())
embedding_model = SentenceTransformer(modules=[_word_embedding_model, _pooling_model])
print("Embedding model ready.")


# ---------------------------------------------------------------------------
# Step 0: Verify the PDF's digital signature (runs FIRST, before anything else)
# ---------------------------------------------------------------------------

class InvalidSignatureError(ValueError):
    """Raised when a PDF is unsigned, was altered after signing, or was signed by an unknown key."""


def verify_pdf_signature(pdf_path: str, public_key_path: str = doc_security.PUBLIC_KEY_PATH) -> str:
    """Returns a success message, or raises InvalidSignatureError."""
    if not os.path.exists(public_key_path):
        raise InvalidSignatureError(
            f"Public key not found at '{public_key_path}'. Cannot verify the sender."
        )

    public_key = doc_security.load_public_key(public_key_path)
    is_valid, message = doc_security.verify_file(pdf_path, public_key)
    if not is_valid:
        raise InvalidSignatureError(message)
    return message


# ---------------------------------------------------------------------------
# Step 1: PDF text extraction
# ---------------------------------------------------------------------------

def extract_text(pdf_path: str) -> str:
    """Reads a PDF file and returns all of its text as one string."""
    reader = PdfReader(pdf_path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


# ---------------------------------------------------------------------------
# Step 2: Legal-aware chunking with fallbacks
# ---------------------------------------------------------------------------

def chunk_text(text: str, chunk_size: int = 200, overlap: int = 40) -> list[str]:

    # Tier 1: numbered clauses
    pattern = r"(?=\n?\s*\d+\.\s)"
    chunks = [c.strip() for c in re.split(pattern, text) if len(c.strip()) > 30]

    if len(chunks) > 1:
        print(f"[chunk_text] Used TIER 1 (numbered clauses) -> {len(chunks)} chunks")
        return chunks

    # Tier 2: paragraph breaks (regex-based, since real PDF extraction rarely
    # produces a perfectly clean "\n\n" -- it's often "\n \n" or similar)
    chunks = [p.strip() for p in re.split(r"\n\s*\n+", text) if len(p.strip()) > 30]

    if len(chunks) > 1:
        print(f"[chunk_text] Used TIER 2 (paragraph breaks) -> {len(chunks)} chunks")
        return chunks

    # Tier 3: fixed-size window fallback
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        if len(chunk.strip()) > 30:
            chunks.append(chunk.strip())
        start += chunk_size - overlap

    print(f"[chunk_text] Used TIER 3 (fixed-size window fallback) -> {len(chunks)} chunks")
    return chunks


# ---------------------------------------------------------------------------
# Step 2.5: Analyze the document and suggest a hybrid search alpha
# ---------------------------------------------------------------------------

def analyze_document(text: str) -> dict:

    words = text.split()
    word_count = max(len(words), 1)  # avoid division by zero

    # Patterns that indicate precise, citation-heavy legal text
    citation_patterns = [
        r"\b(?:Section|Sec\.|Article|Art\.|Clause|Rule)\s*\d+[A-Za-z]?",
        r"\bIPC\b|\bCrPC\b|\bCPC\b",
        r"\b\d{4}\s*\(\d+\)|\bAIR\s*\d{4}",   # e.g. case citation year patterns
        r"\bv\.\s+[A-Z][a-zA-Z]+",             # "X v. Y" case naming
    ]

    citation_hits = 0
    for pattern in citation_patterns:
        citation_hits += len(re.findall(pattern, text))

    # Density of citation-like terms relative to document length
    density = citation_hits / word_count * 100  # hits per 100 words

    if density >= 1.5:
        suggested_alpha = 0.3
        label = "Citation-heavy document"
        reasoning = (
            f"Found {citation_hits} section/article/case-citation references "
            f"in this document ({density:.2f} per 100 words). Since exact terms "
            "like section numbers matter a lot here, keyword-weighted search "
            "is recommended."
        )
    elif density <= 0.3:
        suggested_alpha = 0.7
        label = "Narrative / conceptual document"
        reasoning = (
            f"Found very few explicit citations ({citation_hits} total, "
            f"{density:.2f} per 100 words). This document reads more "
            "narratively, so semantic (meaning-based) search is "
            "recommended to catch paraphrased questions."
        )
    else:
        suggested_alpha = 0.5
        label = "Balanced document"
        reasoning = (
            f"Found a moderate number of citations ({citation_hits} total, "
            f"{density:.2f} per 100 words), so an equal balance of keyword "
            "and semantic search is recommended."
        )

    return {
        "suggested_alpha": suggested_alpha,
        "label": label,
        "reasoning": reasoning,
        "citation_hits": citation_hits,
    }


# ---------------------------------------------------------------------------
# Step 3: Weaviate collection management
# ---------------------------------------------------------------------------

def get_client():
    """Opens a connection to the local Weaviate instance."""
    return weaviate.connect_to_local()


def ensure_collection(client):
    """Creates the LegalDocs collection (schema) if it doesn't already exist."""
    if not client.collections.exists(COLLECTION_NAME):
        client.collections.create(
            name=COLLECTION_NAME,
            vectorizer_config=wvc.config.Configure.Vectorizer.none(),
            properties=[
                wvc.config.Property(name="text", data_type=wvc.config.DataType.TEXT),
                wvc.config.Property(name="source", data_type=wvc.config.DataType.TEXT),
                wvc.config.Property(name="section", data_type=wvc.config.DataType.TEXT),
            ],
        )


def flush_collection(client):
    """Deletes all previously stored chunks -- used when a new PDF replaces the old one."""
    collection = client.collections.get(COLLECTION_NAME)
    collection.data.delete_many(
        where=wvc.query.Filter.by_property("source").like("*")
    )


# ---------------------------------------------------------------------------
# Step 4: Embed + store chunks in Weaviate
# ---------------------------------------------------------------------------

def embed_and_store(chunks: list[str], source_filename: str) -> int:

    client = get_client()
    try:
        ensure_collection(client)
        flush_collection(client)

        collection = client.collections.get(COLLECTION_NAME)
        for i, chunk in enumerate(chunks):
            vector = embedding_model.encode(chunk).tolist()
            collection.data.insert(
                properties={
                    "text": chunk,
                    "source": source_filename,
                    "section": f"chunk_{i}",
                },
                vector=vector,
            )
    finally:
        client.close()

    return len(chunks)


# ---------------------------------------------------------------------------
# Step 5: The full pipeline, wrapped in one function
# ---------------------------------------------------------------------------

def run_ingestion_pipeline(pdf_path: str) -> dict:

    filename = os.path.basename(pdf_path)

    # Step 0: integrity + authenticity check BEFORE anything is read, flushed or stored.
    if REQUIRE_SIGNATURE:
        print(f"[*] Verifying digital signature of '{filename}'...")
        message = verify_pdf_signature(pdf_path)
        print(f" [OK] {message}")

    text = extract_text(pdf_path)
    if not text.strip():
        raise ValueError("Could not extract text from this PDF (it may be scanned/image-based).")

    chunks = chunk_text(text)
    if not chunks:
        raise ValueError("No usable text chunks found in this PDF.")

    num_stored = embed_and_store(chunks, filename)
    analysis = analyze_document(text)

    return {
        "filename": filename,
        "signature_verified": REQUIRE_SIGNATURE,
        "characters_extracted": len(text),
        "chunks_indexed": num_stored,
        "suggested_alpha": analysis["suggested_alpha"],
        "search_type_label": analysis["label"],
        "reasoning": analysis["reasoning"],
    }


# ---------------------------------------------------------------------------
# Allow standalone testing: python rag_pipeline.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_pdf = "test1.pdf"  # change to your test file
    try:
        result = run_ingestion_pipeline(test_pdf)
        print(result)
    except InvalidSignatureError as e:
        print(f"[x] Document REJECTED: {e}")
        print("    Nothing was indexed.")