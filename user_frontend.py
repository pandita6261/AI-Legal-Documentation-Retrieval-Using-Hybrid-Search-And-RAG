import html as html_lib
import urllib.parse
from string import Template
import requests
import streamlit as st

# ============================================================
# LEGAL AI — High-Contrast, Production Streamlit Frontend
# Compatible with FastAPI RAG backend:
#   POST /upload
#   POST /ask
#   POST /search-preference
#
# Run:
#   streamlit run legal_ai_frontend.py
# ============================================================

BACKEND_DEFAULT = "http://127.0.0.1:8000"
REQUEST_TIMEOUT = 180

st.set_page_config(
    page_title="Legal AI | Document Intelligence",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------- SESSION STATE -------------------------
DEFAULT_STATE = {
    "messages": [],
    "document_ready": False,
    "document_name": None,
    "upload_result": None,
    "active_alpha": 0.5,
    "pending_prompt": None,
    "theme": "dark",
    "upload_widget_version": 0,
    "backend_url_input": BACKEND_DEFAULT,
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value

# ------------------------- THEME DEFINITIONS -------------------------
THEMES = {
    "dark": {
        "bg": "#0B0E14",
        "bg_soft": "#111620",
        "panel": "#181F2C",
        "panel_border": "#283446",
        "ink": "#F3F5F9",
        "ink_muted": "#A2B0C6",
        "ink_faint": "#6D7B93",
        "accent": "#E5B842",
        "accent_hover": "#F5C752",
        "accent_ink": "#141107",
        "accent_soft": "rgba(229, 184, 66, 0.16)",
        "user_bubble": "#1E2736",
        "user_bubble_border": "#313E53",
        "user_bubble_ink": "#FFFFFF",
        "card_hover_border": "#E5B842",
        "code_bg": "#141A24",
        "tag_bg": "rgba(229, 184, 66, 0.14)",
        "tag_ink": "#F3C552",
        "success_bg": "rgba(46, 160, 67, 0.15)",
        "success_ink": "#3FB950",
    },
    "light": {
        "bg": "#F8F9FA",
        "bg_soft": "#EFF2F6",
        "panel": "#FFFFFF",
        "panel_border": "#D5DCE5",
        "ink": "#111827",
        "ink_muted": "#4B5563",
        "ink_faint": "#6B7280",
        "accent": "#0F5B46",
        "accent_hover": "#0C4837",
        "accent_ink": "#FFFFFF",
        "accent_soft": "rgba(15, 91, 70, 0.10)",
        "user_bubble": "#0F5B46",
        "user_bubble_border": "#0C4837",
        "user_bubble_ink": "#FFFFFF",
        "card_hover_border": "#0F5B46",
        "code_bg": "#F1F4F9",
        "tag_bg": "rgba(15, 91, 70, 0.10)",
        "tag_ink": "#0F5B46",
        "success_bg": "rgba(16, 149, 106, 0.12)",
        "success_ink": "#0F5B46",
    },
}

CSS_TEMPLATE = """
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700&family=Inter:wght@400;500;600;700&display=swap');

:root {
  --bg: $bg;
  --bg-soft: $bg_soft;
  --panel: $panel;
  --panel-border: $panel_border;
  --ink: $ink;
  --ink-muted: $ink_muted;
  --ink-faint: $ink_faint;
  --accent: $accent;
  --accent-hover: $accent_hover;
  --accent-ink: $accent_ink;
  --accent-soft: $accent_soft;
  --user-bubble: $user_bubble;
  --user-bubble-border: $user_bubble_border;
  --user-bubble-ink: $user_bubble_ink;
  --code-bg: $code_bg;
  --tag-bg: $tag_bg;
  --tag-ink: $tag_ink;
  --success-bg: $success_bg;
  --success-ink: $success_ink;
  --card-hover-border: $card_hover_border;
}

/* Base resets & typography */
html, body, .stApp {
  background-color: var(--bg) !important;
  color: var(--ink) !important;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
  -webkit-font-smoothing: antialiased;
}

h1, h2, h3, .brand-title {
  font-family: 'Cinzel', Georgia, serif !important;
  letter-spacing: -0.01em;
  color: var(--ink) !important;
}

p, span, label, div {
  color: inherit;
}

/* Chrome UI cleanup */
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] {
  display: none !important;
}

[data-testid="stHeader"] {
  background: var(--bg) !important;
  border-bottom: 1px solid var(--panel-border);
}

.block-container {
  max-width: 900px !important;
  padding: 1.8rem 1.5rem 8rem !important;
}

/* Sidebar styling */
[data-testid="stSidebar"] {
  background-color: var(--bg-soft) !important;
  border-right: 1px solid var(--panel-border) !important;
}

[data-testid="stSidebar"] .block-container {
  padding: 1.5rem 1rem 3rem !important;
}

.side-header {
  font-size: 0.72rem;
  letter-spacing: 0.1em;
  font-weight: 700;
  color: var(--ink-faint);
  margin: 1.4rem 0 0.5rem 0;
  text-transform: uppercase;
}

/* Custom inputs & forms */
[data-testid="stTextInput"] input {
  background: var(--panel) !important;
  color: var(--ink) !important;
  border: 1px solid var(--panel-border) !important;
  border-radius: 8px !important;
  padding: 8px 12px;
}
[data-testid="stTextInput"] input:focus {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 2px var(--accent-soft) !important;
}

[data-testid="stFileUploader"] {
  background: var(--panel) !important;
  border: 1px dashed var(--panel-border) !important;
  border-radius: 12px !important;
  padding: 8px;
}
[data-testid="stFileUploader"] label {
  color: var(--ink) !important;
  font-weight: 600 !important;
}

/* Compact, clean buttons */
.stButton button {
  background-color: var(--panel) !important;
  color: var(--ink) !important;
  border: 1px solid var(--panel-border) !important;
  border-radius: 8px !important;
  font-weight: 600 !important;
  font-size: 0.85rem !important;
  min-height: 2.2rem !important;
  padding: 0.25rem 0.85rem !important;
  transition: all 0.15s ease-in-out !important;
}

.stButton button:hover {
  border-color: var(--accent) !important;
  color: var(--accent) !important;
  transform: translateY(-1px);
}

.stButton button[kind="primary"] {
  background-color: var(--accent) !important;
  color: var(--accent-ink) !important;
  border: 1px solid var(--accent) !important;
}
.stButton button[kind="primary"]:hover {
  background-color: var(--accent-hover) !important;
  color: var(--accent-ink) !important;
}

/* Chat area & message styling */
[data-testid="stChatMessage"] {
  background-color: transparent !important;
  padding: 0.8rem 0 !important;
}

[data-testid="stChatMessageContent"] {
  color: var(--ink) !important;
  font-size: 0.98rem !important;
  line-height: 1.68 !important;
}

/* User message box */
.user-msg-box {
  background: var(--user-bubble);
  color: var(--user-bubble-ink) !important;
  border: 1px solid var(--user-bubble-border);
  padding: 12px 18px;
  border-radius: 16px 16px 2px 16px;
  margin-left: auto;
  max-width: 82%;
  line-height: 1.6;
  font-size: 0.96rem;
  word-break: break-word;
}

/* Code tags */
code {
  background: var(--code-bg) !important;
  color: var(--accent) !important;
  padding: 2px 6px !important;
  border-radius: 5px !important;
  font-size: 0.88em !important;
}

/* Expanders */
[data-testid="stExpander"] {
  background: var(--panel) !important;
  border: 1px solid var(--panel-border) !important;
  border-radius: 12px !important;
}
[data-testid="stExpander"] summary {
  color: var(--ink) !important;
  font-weight: 600 !important;
}

/* Hero & suggestion cards */
.prompt-card {
  background: var(--panel);
  border: 1px solid var(--panel-border);
  border-radius: 14px;
  padding: 18px 16px;
  min-height: 110px;
  transition: all 0.2s ease;
  margin-bottom: 8px;
}
.prompt-card:hover {
  border-color: var(--card-hover-border);
}
.prompt-kicker {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--accent);
  text-transform: uppercase;
  margin-bottom: 4px;
}
.prompt-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--ink);
  line-height: 1.4;
}

/* Citations */
.citation-box {
  background: var(--bg-soft);
  border-left: 3px solid var(--accent);
  padding: 10px 14px;
  margin: 6px 0;
  border-radius: 0 8px 8px 0;
  font-size: 0.88rem;
  color: var(--ink-muted);
}

/* Status badge pills */
.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
}
.status-pill.verified {
  background: var(--success-bg);
  color: var(--success-ink);
}
.status-pill.neutral {
  background: var(--tag-bg);
  color: var(--tag-ink);
}

/* Bottom Chat Input */
[data-testid="stChatInput"] {
  background-color: var(--panel) !important;
  border: 1px solid var(--panel-border) !important;
  border-radius: 20px !important;
  color: var(--ink) !important;
}
[data-testid="stChatInput"]:focus-within {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 2px var(--accent-soft) !important;
}
[data-testid="stChatInput"] textarea {
  color: var(--ink) !important;
}
"""


def inject_styles():
    theme_vars = THEMES[st.session_state.theme]
    css_string = Template(CSS_TEMPLATE).substitute(**theme_vars)
    st.markdown(f"<style>{css_string}</style>", unsafe_allow_html=True)


inject_styles()


# ------------------------- API & UTILITY HELPERS -------------------------
def get_backend_url() -> str:
    url = st.session_state.get("backend_url_input", BACKEND_DEFAULT).strip()
    return url.rstrip("/")


def extract_error_detail(response: requests.Response) -> str:
    try:
        data = response.json()
        if isinstance(data, dict):
            return data.get("detail") or data.get("message") or response.text
        return response.text
    except Exception:
        return response.text or f"HTTP {response.status_code} Error"


def handle_network_error(err: Exception):
    if isinstance(err, requests.exceptions.ConnectionError):
        st.error("🔌 Could not connect to RAG backend. Ensure your FastAPI server is running.")
    elif isinstance(err, requests.exceptions.Timeout):
        st.error("⏳ Request timed out. The document may be too large or the LLM is busy.")
    else:
        st.error(f"⚠️ Network error: {err}")


def reset_workspace():
    st.session_state.messages = []
    st.session_state.document_ready = False
    st.session_state.document_name = None
    st.session_state.upload_result = None
    st.session_state.active_alpha = 0.5
    st.session_state.pending_prompt = None
    st.session_state.upload_widget_version += 1


def api_upload_document(pdf_file, sig_file):
    files = {"file": (pdf_file.name, pdf_file.getvalue(), "application/pdf")}
    if sig_file is not None:
        files["signature"] = (
            sig_file.name,
            sig_file.getvalue(),
            "application/octet-stream",
        )
    return requests.post(
        f"{get_backend_url()}/upload",
        files=files,
        timeout=REQUEST_TIMEOUT,
    )


def api_update_alpha(alpha: float):
    return requests.post(
        f"{get_backend_url()}/search-preference",
        json={"alpha": alpha},
        timeout=15,
    )


def api_ask_question(question: str):
    return requests.post(
        f"{get_backend_url()}/ask",
        json={"question": question, "top_k": 5},
        timeout=REQUEST_TIMEOUT,
    )


def get_assistant_avatar_uri() -> str:
    theme = THEMES[st.session_state.theme]
    svg = (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>"
        f"<rect width='64' height='64' rx='16' fill='{theme['accent']}'/>"
        f"<text x='32' y='44' font-family='Georgia, serif' font-size='34' font-weight='bold' "
        f"text-anchor='middle' fill='{theme['accent_ink']}'>&#167;</text></svg>"
    )
    return "data:image/svg+xml;utf8," + urllib.parse.quote(svg)


def render_citations(citations: list):
    if not citations:
        return
    with st.expander(f"📚 Verified Sources & Passages ({len(citations)})", expanded=False):
        for idx, item in enumerate(citations, 1):
            if isinstance(item, dict):
                page_info = f" — Page {item['page']}" if "page" in item else ""
                score_info = f" (Score: {item['score']:.2f})" if "score" in item else ""
                content = item.get("text") or item.get("content") or str(item)
                st.markdown(
                    f'<div class="citation-box"><strong>[{idx}]{page_info}{score_info}</strong><br/>'
                    f"{html_lib.escape(content)}</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="citation-box"><strong>[{idx}]</strong> '
                    f"{html_lib.escape(str(item))}</div>",
                    unsafe_allow_html=True,
                )


def export_transcript_markdown() -> str:
    lines = [
        f"# Legal AI Transcript — {st.session_state.document_name or 'Document'}",
        "",
    ]
    for msg in st.session_state.messages:
        role = "User" if msg["role"] == "user" else "Legal AI Assistant"
        lines.append(f"### {role}\n{msg['content']}\n")
        if msg.get("citations"):
            lines.append("**Sources Referenced:**")
            for c in msg["citations"]:
                lines.append(f"- {c}")
            lines.append("")
    return "\n".join(lines)


# ------------------------- SIDEBAR -------------------------
with st.sidebar:
    st.markdown('<div class="brand-title" style="font-size: 1.4rem;">⚖️ LEGAL AI</div>', unsafe_allow_html=True)
    st.caption("Verifiable Legal Retrieval & Reasoning")

    # Dark / Light Theme Toggle
    theme_val = st.toggle("Dark Mode", value=(st.session_state.theme == "dark"))
    active_theme = "dark" if theme_val else "light"
    if active_theme != st.session_state.theme:
        st.session_state.theme = active_theme
        st.rerun()

    if st.button("＋ Start New Chat", use_container_width=True):
        reset_workspace()
        st.rerun()

    st.markdown('<div class="side-header">Server Connection</div>', unsafe_allow_html=True)
    st.text_input(
        "Backend Base URL",
        value=st.session_state.backend_url_input,
        key="backend_url_input",
        help="FastAPI application root address.",
    )

    st.markdown('<div class="side-header">Document Ingestion</div>', unsafe_allow_html=True)
    sidebar_pdf = st.file_uploader(
        "Upload PDF",
        type=["pdf"],
        key=f"side_pdf_{st.session_state.upload_widget_version}",
    )
    sidebar_sig = st.file_uploader(
        "Digital Signature (.sig)",
        type=["sig"],
        key=f"side_sig_{st.session_state.upload_widget_version}",
        help="Optional detached cryptographic signature file.",
    )

    if st.button("Verify & Ingest PDF", type="primary", use_container_width=True, disabled=sidebar_pdf is None):
        try:
            with st.spinner("Cryptographically verifying & indexing chunks..."):
                resp = api_upload_document(sidebar_pdf, sidebar_sig)
            if resp.ok:
                data = resp.json()
                st.session_state.document_ready = True
                st.session_state.document_name = sidebar_pdf.name
                st.session_state.upload_result = data
                st.session_state.messages = []
                suggestion = data.get("search_suggestion", {})
                st.session_state.active_alpha = float(suggestion.get("suggested_alpha", 0.5))
                st.success("Document indexed successfully.")
                st.rerun()
            else:
                st.error(f"Ingestion failed ({resp.status_code}): {extract_error_detail(resp)}")
        except Exception as e:
            handle_network_error(e)

    # Details for loaded document
    if st.session_state.document_ready:
        st.markdown('<div class="side-header">Active Document</div>', unsafe_allow_html=True)
        meta = st.session_state.upload_result or {}

        st.markdown(f"**{st.session_state.document_name}**")
        if meta.get("signature_verified"):
            st.markdown('<div class="status-pill verified">✓ Cryptographically Verified</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="status-pill neutral">○ Indexed (Unsigned)</div>', unsafe_allow_html=True)

        chunks_ct = meta.get("chunks_indexed")
        if chunks_ct is not None:
            st.caption(f"Index Size: {chunks_ct} text vectors")

        with st.expander("Search Weights (Hybrid Search)", expanded=False):
            alpha = st.slider(
                "Dense (Semantic) vs Sparse (Keyword)",
                min_value=0.0,
                max_value=1.0,
                value=float(st.session_state.active_alpha),
                step=0.05,
                help="0.0 = BM25 keyword matching only. 1.0 = Pure vector semantic search.",
            )
            pct_sem = int(alpha * 100)
            st.caption(f"BM25: {100 - pct_sem}% | Dense: {pct_sem}%")

            if st.button("Update Weights", use_container_width=True):
                try:
                    res = api_update_alpha(alpha)
                    if res.ok:
                        st.session_state.active_alpha = alpha
                        st.toast("Hybrid search weight updated.")
                    else:
                        st.error(extract_error_detail(res))
                except Exception as e:
                    handle_network_error(e)

    if st.session_state.messages:
        st.markdown('<div class="side-header">Export</div>', unsafe_allow_html=True)
        st.download_button(
            "Download Transcript (.md)",
            data=export_transcript_markdown(),
            file_name=f"{st.session_state.document_name or 'chat'}_analysis.md",
            mime="text/markdown",
            use_container_width=True,
        )


# ------------------------- MAIN VIEW ROUTING -------------------------

# State 1: Upload Prompting (No document active)
if not st.session_state.document_ready:
    st.markdown('<div class="brand-title" style="font-size: 2.2rem; margin-top: 1rem;">Legal Document Intelligence</div>', unsafe_allow_html=True)
    st.markdown(
        "<p style='color: var(--ink-muted); font-size: 1.05rem;'>Upload any legal contract, judicial opinion, or statute to execute verifiable, cited hybrid Q&A.</p>",
        unsafe_allow_html=True,
    )

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(
            """
            <div class="prompt-card">
                <div class="prompt-kicker">Comprehensive Extraction</div>
                <div class="prompt-title">Synthesize Key Liabilities & Obligations</div>
                <div style="font-size: 0.84rem; color: var(--ink-muted); margin-top: 4px;">
                    Summarizes indemnification, termination clauses, and covenants automatically.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_b:
        st.markdown(
            """
            <div class="prompt-card">
                <div class="prompt-kicker">Precision Discovery</div>
                <div class="prompt-title">Locate Critical Dates & Breach Thresholds</div>
                <div style="font-size: 0.84rem; color: var(--ink-muted); margin-top: 4px;">
                    Pinpoints cure periods, renewal windows, and cross-default conditions.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.subheader("Select PDF File to Index")

    mp_pdf = st.file_uploader("Document PDF", type=["pdf"], key=f"main_pdf_{st.session_state.upload_widget_version}")
    mp_sig = st.file_uploader("Detached Signature (.sig)", type=["sig"], key=f"main_sig_{st.session_state.upload_widget_version}")

    if st.button("Index and Open Document", type="primary", use_container_width=True, disabled=mp_pdf is None):
        try:
            with st.spinner("Analyzing document and generating index representations..."):
                response = api_upload_document(mp_pdf, mp_sig)
            if response.ok:
                data = response.json()
                st.session_state.document_ready = True
                st.session_state.document_name = mp_pdf.name
                st.session_state.upload_result = data
                st.session_state.messages = []
                sugg = data.get("search_suggestion", {})
                st.session_state.active_alpha = float(sugg.get("suggested_alpha", 0.5))
                st.rerun()
            else:
                st.error(f"Error ({response.status_code}): {extract_error_detail(response)}")
        except Exception as e:
            handle_network_error(e)


# State 2: Active Chat Interface
else:
    # 1. Spacer to push the top bar lower down on the screen
    st.markdown("<div style='margin-top: 1.8rem;'></div>", unsafe_allow_html=True)

    # 2. Vertically centered action bar (Streamlit native vertical_alignment)
    bar_col1, bar_col2 = st.columns([5, 2], vertical_alignment="center")

    with bar_col1:
        st.markdown(
            f"""
            <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
                <span style="font-size: 0.95rem;"><strong>Active Document:</strong> <code>{html_lib.escape(st.session_state.document_name or '')}</code></span>
                <span class="status-pill neutral">α: {st.session_state.active_alpha}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with bar_col2:
        if st.button("🔄 Change Document", use_container_width=True, key="action_change_doc"):
            reset_workspace()
            st.rerun()

    # Subtle divider separating the action bar from chat history
    st.markdown("<hr style='margin: 12px 0 20px 0; border: none; border-top: 1px solid var(--panel-border);'>", unsafe_allow_html=True)

    # Check for pending prompt before rendering cards to prevent ghosting
    prompt_to_execute = None
    if st.session_state.pending_prompt:
        prompt_to_execute = st.session_state.pending_prompt
        st.session_state.pending_prompt = None

    # Starter prompts (only displayed before conversation starts)
    if len(st.session_state.messages) == 0 and prompt_to_execute is None:
        st.markdown(
            "<p style='color: var(--ink-muted); font-size: 1.02rem; margin-top: 0.5rem;'>"
            "Select an analysis objective below or ask a custom question.</p>",
            unsafe_allow_html=True,
        )

        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            if st.button("📋 Executive Summary\n\nMain covenants & terms", use_container_width=True):
                st.session_state.pending_prompt = (
                    "Summarize this document. Identify key parties, primary obligations, and governing law."
                )
                st.rerun()
        with sc2:
            if st.button("⚠️ Risk & Liabilities\n\nIndemnity & termination", use_container_width=True):
                st.session_state.pending_prompt = (
                    "Highlight all indemnities, warranties, limitations of liability, and termination clauses."
                )
                st.rerun()
        with sc3:
            if st.button("📅 Dates & Deadlines\n\nNotice & cure periods", use_container_width=True):
                st.session_state.pending_prompt = (
                    "Extract all critical dates, milestones, expiration dates, and notification periods."
                )
                st.rerun()

    # Render Historical Messages
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(
                f'<div class="user-msg-box">{html_lib.escape(msg["content"])}</div>',
                unsafe_allow_html=True,
            )
        else:
            with st.chat_message("assistant", avatar=get_assistant_avatar_uri()):
                st.markdown(msg["content"])
                render_citations(msg.get("citations", []))

    # User Input Handling
    typed_prompt = st.chat_input("Ask a question about this legal document...")
    current_prompt = prompt_to_execute or typed_prompt

    if current_prompt:
        # Display user message
        st.session_state.messages.append({"role": "user", "content": current_prompt})
        st.markdown(
            f'<div class="user-msg-box">{html_lib.escape(current_prompt)}</div>',
            unsafe_allow_html=True,
        )

        # Call RAG backend
        with st.chat_message("assistant", avatar=get_assistant_avatar_uri()):
            with st.spinner("Analyzing verified document chunks..."):
                try:
                    res = api_ask_question(current_prompt)
                    if res.ok:
                        payload = res.json()
                        reply = payload.get("answer", "No answer could be synthesized.")
                        cites = payload.get("citations", [])

                        st.markdown(reply)
                        render_citations(cites)

                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": reply,
                            "citations": cites,
                        })
                    else:
                        err_text = f"Backend Error ({res.status_code}): {extract_error_detail(res)}"
                        st.error(err_text)
                        st.session_state.messages.append({"role": "assistant", "content": err_text})
                except Exception as e:
                    handle_network_error(e)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": "A network interruption occurred while connecting to the RAG backend.",
                    })