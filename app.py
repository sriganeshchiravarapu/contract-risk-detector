import streamlit as st
import pdfplumber
import json
import requests
import google.generativeai as genai

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Contract Risk Detector",
    page_icon="⚖️",
    layout="wide",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;700;800&family=IBM+Plex+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Mono', monospace;
    background-color: #0d0d0d;
    color: #e8e0d0;
}

h1, h2, h3, .display-font {
    font-family: 'Syne', sans-serif;
}

.stApp { background-color: #0d0d0d; }

/* Header banner */
.hero-banner {
    background: linear-gradient(135deg, #1a0a00 0%, #0d0d0d 50%, #001a0d 100%);
    border: 1px solid #3a2a1a;
    border-radius: 4px;
    padding: 2.5rem 2rem;
    margin-bottom: 2rem;
    position: relative;
    overflow: hidden;
}
.hero-banner::before {
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: repeating-linear-gradient(
        45deg,
        transparent,
        transparent 40px,
        rgba(255,100,0,0.02) 40px,
        rgba(255,100,0,0.02) 41px
    );
}
.hero-title {
    font-family: 'Syne', sans-serif;
    font-size: 2.6rem;
    font-weight: 800;
    color: #ff6a00;
    letter-spacing: -1px;
    line-height: 1.1;
    margin: 0;
}
.hero-sub {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.78rem;
    color: #6a5a4a;
    margin-top: 0.5rem;
    letter-spacing: 2px;
    text-transform: uppercase;
}

/* Stage labels */
.stage-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.65rem;
    letter-spacing: 3px;
    text-transform: uppercase;
    color: #ff6a00;
    border-left: 2px solid #ff6a00;
    padding-left: 10px;
    margin-bottom: 0.75rem;
    display: block;
}

/* Output cards */
.output-card {
    background: #141414;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    padding: 1.25rem;
    margin-bottom: 1rem;
}
.output-card-title {
    font-family: 'Syne', sans-serif;
    font-size: 0.8rem;
    font-weight: 700;
    color: #8a7a6a;
    text-transform: uppercase;
    letter-spacing: 2px;
    margin-bottom: 0.75rem;
}
.output-card-content {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.82rem;
    line-height: 1.7;
    color: #c8c0b0;
    white-space: pre-wrap;
}

/* Risk badge */
.risk-high   { color: #ff4444; font-weight: 700; }
.risk-medium { color: #ffaa00; font-weight: 700; }
.risk-low    { color: #44cc88; font-weight: 700; }

/* Status pill */
.status-sent     { background:#0a2a1a; border:1px solid #44cc88; color:#44cc88; padding:4px 14px; border-radius:2px; font-size:0.75rem; letter-spacing:2px; }
.status-not-sent { background:#2a1a0a; border:1px solid #ffaa00; color:#ffaa00; padding:4px 14px; border-radius:2px; font-size:0.75rem; letter-spacing:2px; }
.status-error    { background:#2a0a0a; border:1px solid #ff4444; color:#ff4444; padding:4px 14px; border-radius:2px; font-size:0.75rem; letter-spacing:2px; }

/* Override Streamlit button */
div.stButton > button {
    background: #ff6a00;
    color: #0d0d0d;
    border: none;
    border-radius: 2px;
    font-family: 'Syne', sans-serif;
    font-weight: 700;
    font-size: 0.85rem;
    letter-spacing: 1px;
    padding: 0.6rem 1.6rem;
    cursor: pointer;
    transition: background 0.2s;
}
div.stButton > button:hover { background: #ff8c3a; }

/* File uploader */
[data-testid="stFileUploader"] {
    background: #141414;
    border: 1px dashed #3a2a1a;
    border-radius: 4px;
}

/* Text input */
.stTextInput input, .stTextArea textarea {
    background: #141414 !important;
    border: 1px solid #2a2a2a !important;
    color: #e8e0d0 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    border-radius: 2px !important;
}

div[data-testid="stExpander"] {
    background: #141414;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
}

hr { border-color: #1e1e1e; }

.separator { border-top: 1px solid #1e1e1e; margin: 2rem 0; }
</style>
""", unsafe_allow_html=True)

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-banner">
  <div class="hero-title">⚖ CONTRACT<br>RISK DETECTOR</div>
  <div class="hero-sub">AI-Powered Document Orchestrator · Gemini + n8n Automation</div>
</div>
""", unsafe_allow_html=True)

# ── Gemini setup ──────────────────────────────────────────────────────────────
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except Exception:
    st.warning("⚠️ Set GEMINI_API_KEY in .streamlit/secrets.toml", icon="🔑")

# ── Helper: extract text ──────────────────────────────────────────────────────
def extract_text(uploaded_file) -> str:
    if uploaded_file.type == "application/pdf":
        with pdfplumber.open(uploaded_file) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)
    return uploaded_file.read().decode("utf-8", errors="ignore")


# ── Helper: Gemini dynamic extraction ────────────────────────────────────────
def gemini_extract(doc_text: str, question: str) -> dict:
    model = genai.GenerativeModel("gemini-2.0-flash")

    prompt = f"""You are a contract risk analysis expert.

DOCUMENT:
\"\"\"
{doc_text[:12000]}
\"\"\"

USER QUESTION: {question}

Task:
1. Identify the 5–8 most relevant key-value pairs from the document that directly help answer the question.
2. Always include a "risk_level" field with value exactly one of: "High", "Medium", or "Low".
3. Always include a "risk_summary" field: a 1-sentence summary of the main risk.

Respond ONLY with a valid JSON object. No markdown, no explanation.
Example shape:
{{
  "risk_level": "High",
  "risk_summary": "...",
  "key1": "value1",
  "key2": "value2"
}}
"""
    response = model.generate_content(prompt)
    raw = response.text.strip()
    # Strip possible code fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


# ── Helper: call n8n webhook ──────────────────────────────────────────────────
def call_n8n(doc_text: str, extracted: dict, question: str, recipient: str) -> dict:
    url = st.secrets["N8N_WEBHOOK_URL"]
    payload = {
        "document_text": doc_text[:6000],
        "extracted_data": extracted,
        "user_question": question,
        "recipient_email": recipient,
    }
    resp = requests.post(url, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()


# ═════════════════════════════════════════════════════════════════════════════
# STAGE 1 — Upload & Question
# ═════════════════════════════════════════════════════════════════════════════
st.markdown('<span class="stage-label">Stage 01 — Document Upload & Query</span>', unsafe_allow_html=True)

col1, col2 = st.columns([1, 1], gap="large")

with col1:
    uploaded_file = st.file_uploader(
        "Upload contract / invoice / agreement",
        type=["pdf", "txt"],
        label_visibility="collapsed",
    )

with col2:
    question = st.text_area(
        "Analytical question",
        placeholder="e.g. What are the termination clauses and associated penalties?",
        height=120,
        label_visibility="collapsed",
    )

st.markdown('<div class="separator"></div>', unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════════════════
# STAGE 2 — Gemini Extraction
# ═════════════════════════════════════════════════════════════════════════════
st.markdown('<span class="stage-label">Stage 02 — Gemini Dynamic Extraction</span>', unsafe_allow_html=True)

extracted_data = st.session_state.get("extracted_data", None)
doc_text = st.session_state.get("doc_text", "")

if st.button("🔍 Analyse Document"):
    if not uploaded_file:
        st.error("Please upload a document first.")
    elif not question.strip():
        st.error("Please enter your analytical question.")
    else:
        with st.spinner("Extracting text and calling Gemini..."):
            try:
                doc_text = extract_text(uploaded_file)
                extracted_data = gemini_extract(doc_text, question)
                st.session_state["extracted_data"] = extracted_data
                st.session_state["doc_text"] = doc_text
                st.session_state["question"] = question
                st.success("Extraction complete.")
            except Exception as e:
                st.error(f"Gemini extraction failed: {e}")

if extracted_data:
    risk = extracted_data.get("risk_level", "").strip()
    risk_class = {"High": "risk-high", "Medium": "risk-medium", "Low": "risk-low"}.get(risk, "")

    st.markdown('<div class="output-card">', unsafe_allow_html=True)
    st.markdown('<div class="output-card-title">① Structured Data Extracted (JSON)</div>', unsafe_allow_html=True)

    # Pretty render
    rows_html = ""
    for k, v in extracted_data.items():
        val_str = str(v)
        if k == "risk_level":
            val_str = f'<span class="{risk_class}">{val_str}</span>'
        rows_html += f"<tr><td style='color:#6a5a4a;padding-right:2rem'>{k}</td><td>{val_str}</td></tr>"

    st.markdown(f"""
    <table style='font-family:"IBM Plex Mono",monospace;font-size:0.8rem;line-height:1.8;width:100%'>
    {rows_html}
    </table>
    """, unsafe_allow_html=True)

    with st.expander("Raw JSON"):
        st.code(json.dumps(extracted_data, indent=2), language="json")

    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="separator"></div>', unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════════════════
# STAGE 3 — Email Automation
# ═════════════════════════════════════════════════════════════════════════════
st.markdown('<span class="stage-label">Stage 03 — Conditional Email Automation (n8n)</span>', unsafe_allow_html=True)

if extracted_data:
    recipient = st.text_input(
        "Recipient Email ID",
        placeholder="legal-team@company.com",
        label_visibility="visible",
    )

    if st.button("📨 Send Alert Mail"):
        if not recipient.strip():
            st.error("Please enter a recipient email address.")
        else:
            with st.spinner("Triggering n8n workflow..."):
                try:
                    n8n_result = call_n8n(
                        doc_text,
                        extracted_data,
                        st.session_state.get("question", question),
                        recipient.strip(),
                    )
                    st.session_state["n8n_result"] = n8n_result
                    st.success("Webhook call complete.")
                except Exception as e:
                    st.session_state["n8n_result"] = {"error": str(e)}
                    st.error(f"n8n webhook error: {e}")
else:
    st.info("Complete Stage 02 first to unlock email automation.")

st.markdown('<div class="separator"></div>', unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════════════════
# STAGE 4 — All Outputs
# ═════════════════════════════════════════════════════════════════════════════
st.markdown('<span class="stage-label">Stage 04 — Results Dashboard</span>', unsafe_allow_html=True)

n8n_result = st.session_state.get("n8n_result", None)

if n8n_result:
    if "error" in n8n_result:
        st.markdown(f'<span class="status-error">⚠ WEBHOOK ERROR: {n8n_result["error"]}</span>', unsafe_allow_html=True)
    else:
        # ── Output ② Final Analytical Answer
        final_answer = n8n_result.get("final_answer", n8n_result.get("answer", "—"))
        st.markdown('<div class="output-card">', unsafe_allow_html=True)
        st.markdown('<div class="output-card-title">② Final Analytical Answer</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="output-card-content">{final_answer}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # ── Output ③ Generated Email Body
        email_body = n8n_result.get("email_body", n8n_result.get("emailBody", ""))
        st.markdown('<div class="output-card">', unsafe_allow_html=True)
        st.markdown('<div class="output-card-title">③ Generated Email Body</div>', unsafe_allow_html=True)
        if email_body:
            st.markdown(f'<div class="output-card-content">{email_body}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="output-card-content" style="color:#6a5a4a">No email body returned — condition not met.</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # ── Output ④ Automation Status
        status = n8n_result.get("status", n8n_result.get("automation_status", "UNKNOWN")).upper()
        pill_class = "status-sent" if "SENT" in status else "status-not-sent"
        st.markdown(f"""
        <div style="margin-top:0.5rem">
          <div class="output-card-title" style="margin-bottom:0.5rem">④ Email Automation Status</div>
          <span class="{pill_class}">{status}</span>
        </div>
        """, unsafe_allow_html=True)

elif extracted_data:
    st.markdown("""
    <div style="color:#3a3a3a;font-size:0.8rem;letter-spacing:1px;text-align:center;padding:2rem">
    AWAITING WEBHOOK TRIGGER — CLICK "SEND ALERT MAIL" ABOVE
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div style="color:#3a3a3a;font-size:0.8rem;letter-spacing:1px;text-align:center;padding:2rem">
    UPLOAD A DOCUMENT AND RUN ANALYSIS TO SEE RESULTS HERE
    </div>
    """, unsafe_allow_html=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center;color:#2a2a2a;font-size:0.65rem;letter-spacing:2px;margin-top:3rem;text-transform:uppercase">
Contract Risk Detector · Gemini 1.5 Flash · n8n Workflow Automation
</div>
""", unsafe_allow_html=True)
