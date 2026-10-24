"""
main.py
-------
The API / backend layer for the legal RAG project.

Endpoints:
  POST /upload             -> upload a PDF + its signature file (.sig); the signature is
                              verified first, and only a valid document is indexed
  POST /search-preference  -> user confirms / overrides the suggested search balance (alpha)
  GET  /search-preference  -> read the current suggestion and the active setting
  POST /ask                -> ask a question about the currently indexed PDF

All PDF verification / extraction / chunking / embedding / storing logic lives in
rag_pipeline.py -- this file receives the files, calls the pipeline, and answers questions.

IMPORTANT: start the server from the project folder (the one that contains keys/),
because the pipeline looks for keys/public_key.pem relative to where it is run:
  venv\\Scripts\\python.exe -m uvicorn main:app --reload
"""

import os
import shutil

import ollama
from fastapi import FastAPI, File, UploadFile, HTTPException
from pydantic import BaseModel

import doc_security
import rag_pipeline  # <-- our ingestion pipeline module

UPLOAD_DIR = "uploaded_docs"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="Legal RAG Backend")

# Simple in-memory state -- fine since this project handles ONE document at a time.
# suggested_alpha: what the analysis recommended after the last upload
# active_alpha: what search will actually use (defaults to the suggestion,
#               but the user can override it via /search-preference)
app_state = {
    "suggested_alpha": 0.5,
    "active_alpha": 0.5,
    "search_type_label": None,
    "reasoning": None,
}


# ---------------------------------------------------------------------------
# Endpoint 1: Upload a PDF + signature -> verify, then run the ingestion pipeline
# ---------------------------------------------------------------------------

@app.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    signature: UploadFile | None = File(None),
):
    # basename() stops a malicious filename like "..\\..\\x.pdf" from escaping the folder
    filename = os.path.basename(file.filename or "")
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    if rag_pipeline.REQUIRE_SIGNATURE and signature is None:
        raise HTTPException(
            status_code=400,
            detail="A signature file (.sig) must be uploaded together with the PDF.",
        )

    pdf_path = os.path.join(UPLOAD_DIR, filename)
    sig_path = doc_security.signature_path_for(pdf_path)  # '<pdf>.sig', the name the pipeline expects

    with open(pdf_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    if signature is not None:
        with open(sig_path, "wb") as f:
            shutil.copyfileobj(signature.file, f)

    try:
        # Step 0 inside the pipeline verifies the signature BEFORE anything is
        # extracted, flushed or stored.
        result = rag_pipeline.run_ingestion_pipeline(pdf_path)
    except rag_pipeline.InvalidSignatureError as e:
        # Rejected: remove the saved files. The previously indexed document
        # (if any) is untouched, because the pipeline stopped before flushing.
        for path in (pdf_path, sig_path):
            if os.path.exists(path):
                os.remove(path)
        raise HTTPException(status_code=403, detail=f"Document rejected: {e}")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Store the suggestion, and default the active search mode to it
    # until/unless the user explicitly overrides it.
    app_state["suggested_alpha"] = result["suggested_alpha"]
    app_state["active_alpha"] = result["suggested_alpha"]
    app_state["search_type_label"] = result["search_type_label"]
    app_state["reasoning"] = result["reasoning"]

    return {
        "status": "success",
        "message": f"'{result['filename']}' verified and indexed successfully.",
        "signature_verified": result["signature_verified"],
        "chunks_indexed": result["chunks_indexed"],
        "search_suggestion": {
            "label": result["search_type_label"],
            "reasoning": result["reasoning"],
            "suggested_alpha": result["suggested_alpha"],
        },
    }


class SearchPreference(BaseModel):
    alpha: float  # 0.0 = pure keyword, 1.0 = pure semantic


@app.post("/search-preference")
async def set_search_preference(payload: SearchPreference):
    """
    Lets the user accept the suggested alpha or set their own value.
    The frontend calls this after showing the suggestion from /upload
    and letting the user confirm or adjust it.
    """
    if not (0.0 <= payload.alpha <= 1.0):
        raise HTTPException(status_code=400, detail="alpha must be between 0.0 and 1.0")

    app_state["active_alpha"] = payload.alpha
    return {"status": "updated", "active_alpha": app_state["active_alpha"]}


@app.get("/search-preference")
async def get_search_preference():
    """Lets the frontend check the current suggestion and active setting."""
    return app_state


# ---------------------------------------------------------------------------
# Endpoint 2: Ask a question -> retrieval + LLM generation
# ---------------------------------------------------------------------------

class QuestionRequest(BaseModel):
    question: str
    top_k: int = 5


@app.post("/ask")
async def ask_question(payload: QuestionRequest):
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    client = rag_pipeline.get_client()
    try:
        if not client.collections.exists(rag_pipeline.COLLECTION_NAME):
            raise HTTPException(status_code=404, detail="No document has been uploaded yet.")

        collection = client.collections.get(rag_pipeline.COLLECTION_NAME)

        # Embed the question and run hybrid search (semantic + keyword)
        query_vector = rag_pipeline.embedding_model.encode(question).tolist()
        results = collection.query.hybrid(
            query=question,
            vector=query_vector,
            limit=payload.top_k,
            alpha=app_state["active_alpha"],  # set via /search-preference, defaults to the analyzed suggestion
        )

        if not results.objects:
            return {
                "answer": "I couldn't find relevant information in the uploaded document to answer this question.",
                "citations": [],
            }

        retrieved_chunks = [obj.properties["text"] for obj in results.objects]
        sources = [obj.properties.get("section", "unknown") for obj in results.objects]
        context_text = "\n\n".join(
            f"[{sec}]: {chunk}" for sec, chunk in zip(sources, retrieved_chunks)
        )

        prompt = f"""You are a legal research assistant. Answer the question using ONLY
the context below. If the context does not contain enough information,
say so clearly instead of guessing. Keep the answer clear and concise.

Context:
{context_text}

Question: {question}
"""

        llm_response = ollama.chat(
            model="phi3",
            messages=[{"role": "user", "content": prompt}],
        )
        answer = llm_response["message"]["content"]

    finally:
        client.close()

    return {
        "answer": answer,
        "citations": sources,
    }


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {"status": "Legal RAG backend is running."}