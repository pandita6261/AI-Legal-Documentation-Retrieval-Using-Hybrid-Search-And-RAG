"""
sender_backend.py  (SENDER SIDE / ISSUING AUTHORITY)
------------------------------------------------------
Run by the sender, i.e. the authority where all the legal documents originate.
It is a separate service from the RAG backend (main.py).

Endpoints:
  POST /sign        -> upload a PDF, get back its signature file (.sig).
                       Needs the X-API-Key header, so only authorized staff can sign.
  POST /verify      -> upload a PDF + its .sig, find out whether the PDF is valid
                       (untouched and signed by this authority). Open to everyone.
  GET  /public-key  -> download the authority's public key (public by design).
                       Receivers put it at keys/public_key.pem for the RAG pipeline.

The PRIVATE key never leaves this service. The PDF is never modified.

Run it on its own port (the RAG backend uses 8000):
  venv\\Scripts\\python.exe -m uvicorn sender_backend:app --port 8001 --reload
"""

import os
import secrets
import shutil
import tempfile

from cryptography.hazmat.primitives import serialization
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response
from fastapi.security import APIKeyHeader

import doc_security

API_KEY_PATH = os.path.join(doc_security.KEYS_DIR, "signing_api_key.txt")


# ---------------------------------------------------------------------------
# Startup: signing keys + API key
# ---------------------------------------------------------------------------

def _load_or_create_private_key():
    if os.path.exists(doc_security.PRIVATE_KEY_PATH):
        print("[*] Loaded existing signing key from ./keys/")
        return doc_security.load_private_key()

    print("[*] No signing key found. Generating RSA 2048-bit key pair...")
    private_key, _ = doc_security.generate_and_save_keys()
    print("[+] Keys saved in ./keys/ (private_key.pem, public_key.pem)")
    return private_key


def _load_or_create_api_key() -> str:
    """The key staff must send in the X-API-Key header to use /sign."""
    env_key = os.environ.get("SIGNING_API_KEY")
    if env_key:
        print("[*] Using the signing API key from the SIGNING_API_KEY environment variable.")
        return env_key

    if os.path.exists(API_KEY_PATH):
        print(f"[*] Signing API key is stored in {API_KEY_PATH}")
        with open(API_KEY_PATH, "r") as f:
            return f.read().strip()

    os.makedirs(doc_security.KEYS_DIR, exist_ok=True)
    key = secrets.token_urlsafe(24)
    with open(API_KEY_PATH, "w") as f:
        f.write(key)
    print(f"[+] Created a signing API key and saved it in {API_KEY_PATH}")
    print(f"    API key: {key}")
    return key


PRIVATE_KEY = _load_or_create_private_key()
PUBLIC_KEY = PRIVATE_KEY.public_key()
SIGNING_API_KEY = _load_or_create_api_key()

app = FastAPI(title="Legal Document Signing Service (Sender Side)")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(provided: str | None = Depends(api_key_header)):
    if not provided or not secrets.compare_digest(provided, SIGNING_API_KEY):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Only authorized staff can sign documents.",
        )


# ---------------------------------------------------------------------------
# POST /sign : the authority signs a PDF
# ---------------------------------------------------------------------------

@app.post("/sign", dependencies=[Depends(require_api_key)])
async def sign_document(file: UploadFile = File(...)):
    filename = os.path.basename(file.filename or "")
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files can be signed.")

    # Work inside a temporary folder that is deleted automatically afterwards.
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = os.path.join(tmp, "document.pdf")
        with open(pdf_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        with open(pdf_path, "rb") as f:
            if f.read(5) != b"%PDF-":
                raise HTTPException(status_code=400, detail="This file is not a valid PDF.")

        doc_hash = doc_security.calculate_file_hash(pdf_path).hex()
        doc_security.sign_file(pdf_path, PRIVATE_KEY)  # writes document.pdf.sig in the temp folder

        with open(doc_security.signature_path_for(pdf_path), "rb") as f:
            signature_bytes = f.read()

    safe_name = filename.replace('"', "")
    return Response(
        content=signature_bytes,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}.sig"',
            "X-Document-SHA256": doc_hash,
        },
    )


# ---------------------------------------------------------------------------
# POST /verify : anyone can check a PDF against its signature
# ---------------------------------------------------------------------------

@app.post("/verify")
async def verify_document(
    file: UploadFile = File(...),
    signature: UploadFile = File(...),
):
    filename = os.path.basename(file.filename or "") or "document.pdf"

    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = os.path.join(tmp, "document.pdf")
        sig_path = os.path.join(tmp, "document.pdf.sig")
        with open(pdf_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        with open(sig_path, "wb") as f:
            shutil.copyfileobj(signature.file, f)

        is_valid, message = doc_security.verify_file(pdf_path, PUBLIC_KEY, sig_path)

    return {"filename": filename, "valid": is_valid, "message": message}


# ---------------------------------------------------------------------------
# GET /public-key : receivers download this to verify documents themselves
# ---------------------------------------------------------------------------

@app.get("/public-key")
async def get_public_key():
    pem = PUBLIC_KEY.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return Response(
        content=pem,
        media_type="application/x-pem-file",
        headers={"Content-Disposition": 'attachment; filename="public_key.pem"'},
    )


@app.get("/")
def root():
    return {"status": "Legal document Digital Signature is running. Use /sign, /verify, or /public-key."}