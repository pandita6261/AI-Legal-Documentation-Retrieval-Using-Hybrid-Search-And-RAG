"""
sign_document.py  (SENDER SIDE)
--------------------------------
Signs a PDF so the RAG system can later verify it.

Usage:
    python sign_document.py <path_to_pdf>

What it does:
  1. Creates an RSA key pair in ./keys/ if one doesn't exist yet
  2. Signs the PDF with the private key
  3. Writes the signature to '<path_to_pdf>.sig'

Keep keys/private_key.pem with the sender only. The RAG system only needs
keys/public_key.pem.
"""

import os
import sys

import doc_security


def main():
    if len(sys.argv) != 2:
        print("Usage: python sign_document.py <path_to_pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    if not os.path.exists(pdf_path):
        print(f"[x] File not found: {pdf_path}")
        sys.exit(1)

    if os.path.exists(doc_security.PRIVATE_KEY_PATH):
        print("[*] Using existing key pair from ./keys/")
        private_key = doc_security.load_private_key()
    else:
        print("[*] No key pair found. Generating RSA 2048-bit key pair...")
        private_key, _ = doc_security.generate_and_save_keys()
        print("[+] Keys saved in ./keys/ (private_key.pem, public_key.pem)")

    signature = doc_security.sign_file(pdf_path, private_key)
    print(f"[+] Signed '{pdf_path}'. Signature ({len(signature)} bytes) saved to "
          f"'{doc_security.signature_path_for(pdf_path)}'")


if __name__ == "__main__":
    main()