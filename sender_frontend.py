import requests
import streamlit as st

st.title("🔐 Legal Document Security")

backend_url = st.sidebar.text_input("Backend URL", "http://127.0.0.1:8001").rstrip("/")

sign_tab, verify_tab, key_tab = st.tabs(["Sign PDF", "Verify PDF", "Public Key"])

# ---------- Sign ----------
with sign_tab:
    api_key = st.text_input("Signing API key", type="password")
    pdf = st.file_uploader("PDF to sign", type=["pdf"], key="sign_pdf")

    if st.button("Sign document"):
        if not api_key or pdf is None:
            st.warning("Enter the API key and choose a PDF.")
        else:
            try:
                r = requests.post(
                    f"{backend_url}/sign",
                    headers={"X-API-Key": api_key},
                    files={"file": (pdf.name, pdf.getvalue(), "application/pdf")},
                    timeout=120,
                )
                if r.ok:
                    st.success("Signature created.")
                    st.download_button("Download .sig", r.content, pdf.name + ".sig")
                else:
                    st.error(f"Signing failed ({r.status_code}): {r.text}")
            except requests.exceptions.RequestException as e:
                st.error(f"Request failed: {e}")

# ---------- Verify ----------
with verify_tab:
    pdf = st.file_uploader("Original PDF", type=["pdf"], key="verify_pdf")
    sig = st.file_uploader("Signature file (.sig)", type=["sig"])

    if st.button("Verify document"):
        if pdf is None or sig is None:
            st.warning("Upload both the PDF and the .sig file.")
        else:
            try:
                r = requests.post(
                    f"{backend_url}/verify",
                    files={
                        "file": (pdf.name, pdf.getvalue(), "application/pdf"),
                        "signature": (sig.name, sig.getvalue()),
                    },
                    timeout=120,
                )
                if r.ok:
                    result = r.json()
                    if result.get("valid"):
                        st.success("Signature is VALID.")
                    else:
                        st.error("Signature is INVALID.")
                    st.write(result.get("message", ""))
                else:
                    st.error(f"Verification failed ({r.status_code}): {r.text}")
            except requests.exceptions.RequestException as e:
                st.error(f"Request failed: {e}")

# ---------- Public key ----------
with key_tab:
    if st.button("Fetch public key"):
        try:
            r = requests.get(f"{backend_url}/public-key", timeout=30)
            if r.ok:
                st.session_state["public_key"] = r.content
            else:
                st.error(f"Could not fetch public key ({r.status_code}).")
        except requests.exceptions.RequestException as e:
            st.error(f"Request failed: {e}")

    if "public_key" in st.session_state:
        st.download_button("Download public_key.pem", st.session_state["public_key"], "public_key.pem")