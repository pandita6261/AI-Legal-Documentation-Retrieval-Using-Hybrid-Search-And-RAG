
import os

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

KEYS_DIR = "keys"
PRIVATE_KEY_PATH = os.path.join(KEYS_DIR, "private_key.pem")
PUBLIC_KEY_PATH = os.path.join(KEYS_DIR, "public_key.pem")


# ---------------------------------------------------------------------------
# Key management
# ---------------------------------------------------------------------------

def generate_and_save_keys(keys_dir: str = KEYS_DIR):
    """Creates a new RSA 2048-bit key pair and saves both keys as PEM files."""
    os.makedirs(keys_dir, exist_ok=True)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    # NOTE: stored unencrypted for simplicity in a college project.
    # In real use, protect it with a password (BestAvailableEncryption).
    with open(os.path.join(keys_dir, "private_key.pem"), "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    with open(os.path.join(keys_dir, "public_key.pem"), "wb") as f:
        f.write(
            private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )

    return private_key, private_key.public_key()


def load_private_key(path: str = PRIVATE_KEY_PATH):
    with open(path, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def load_public_key(path: str = PUBLIC_KEY_PATH):
    with open(path, "rb") as f:
        return serialization.load_pem_public_key(f.read())


# ---------------------------------------------------------------------------
# Hashing, signing, verifying
# ---------------------------------------------------------------------------

def calculate_file_hash(file_path: str) -> bytes:
    """SHA-256 hash of the file, read in 4 KB blocks so large PDFs are fine."""
    digest = hashes.Hash(hashes.SHA256())
    with open(file_path, "rb") as f:
        while chunk := f.read(4096):
            digest.update(chunk)
    return digest.finalize()


def signature_path_for(file_path: str) -> str:
    return file_path + ".sig"


def sign_file(file_path: str, private_key) -> bytes:
    """Signs the PDF's hash with the private key and saves '<file>.sig'."""
    file_hash = calculate_file_hash(file_path)
    signature = private_key.sign(
        file_hash,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH,
        ),
        hashes.SHA256(),
    )
    with open(signature_path_for(file_path), "wb") as f:
        f.write(signature)
    return signature


def verify_file(file_path: str, public_key, signature_path: str | None = None):
    """
    Checks a PDF against its signature file.
    Returns (is_valid: bool, message: str) so callers can decide what to do.
    """
    sig_path = signature_path or signature_path_for(file_path)

    if not os.path.exists(file_path):
        return False, f"File not found: {file_path}"
    if not os.path.exists(sig_path):
        return False, f"No signature file found ({sig_path}). Unsigned documents are not accepted."

    with open(sig_path, "rb") as f:
        signature = f.read()

    file_hash = calculate_file_hash(file_path)
    try:
        public_key.verify(
            signature,
            file_hash,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        return True, "VALID: document integrity intact and sender authenticated."
    except InvalidSignature:
        return False, "INVALID: signature check failed (file was altered, or signed with a different key)."