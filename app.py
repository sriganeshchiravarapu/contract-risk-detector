import streamlit as st
import pdfplumber
import json
import requests
from google import genai

# ✅ Create Gemini client (NEW SDK)
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

# ── Page config ─────────────────────────────────────────
st.set_page_config(
    page_title="Contract Risk Detector",
    page_icon="⚖️",
    layout="wide",
)

st.title("⚖️ Contract Risk Detector")

# ── Extract text ────────────────────────────────────────
def extract_text(uploaded_file):
    if uploaded_file.type == "application/pdf":
        with pdfplumber.open(uploaded_file) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)
    return uploaded_file.read().decode("utf-8", errors="ignore")


# ── Gemini Extraction (FIXED) ───────────────────────────
def gemini_extract(doc_text, question):

    prompt = f"""
    You are a contract risk analysis expert.

    DOCUMENT:
    {doc_text[:12000]}

    QUESTION:
    {question}

    Extract key fields and return JSON:
    {{
        "party_1": "...",
        "party_2": "...",
        "payment_terms": "...",
        "termination_clause": "...",
        "liability_clause": "...",
        "risk_level": "Low/Medium/High",
        "risk_summary": "one line summary"
    }}
    """

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt
    )

    raw = response.text.strip()

    # Clean markdown if present
    if raw.startswith("```"):
        raw = raw.replace("```json", "").replace("```", "")

    return json.loads(raw)


# ── n8n Webhook ─────────────────────────────────────────
def call_n8n(doc_text, extracted, question, recipient):
    url = st.secrets["N8N_WEBHOOK_URL"]

    payload = {
        "document_text": doc_text[:6000],
        "extracted_data": extracted,
        "user_question": question,
        "recipient_email": recipient,
    }

    res = requests.post(url, json=payload)

    return res.json()


# ── UI ──────────────────────────────────────────────────

uploaded_file = st.file_uploader("Upload Contract", type=["pdf", "txt"])
question = st.text_area("Ask your question")

if st.button("🔍 Analyse Document"):

    if not uploaded_file:
        st.error("Upload a file")
    elif not question:
        st.error("Enter question")
    else:
        with st.spinner("Analyzing..."):
            text = extract_text(uploaded_file)

            try:
                data = gemini_extract(text, question)
                st.session_state["data"] = data
                st.session_state["text"] = text
                st.session_state["question"] = question

                st.success("Extraction done")

            except Exception as e:
                st.error(f"Error: {e}")


# ── Show extracted data ─────────────────────────────────
if "data" in st.session_state:

    data = st.session_state["data"]

    st.subheader("📊 Extracted Data")
    st.json(data)

    # Risk highlight
    risk = data.get("risk_level", "")

    if risk == "High":
        st.error("⚠ HIGH RISK")
    elif risk == "Medium":
        st.warning("⚠ MEDIUM RISK")
    else:
        st.success("✔ LOW RISK")

    # Email input
    email = st.text_input("Enter email for alert")

    if st.button("📨 Send Alert Mail"):

        try:
            result = call_n8n(
                st.session_state["text"],
                data,
                st.session_state["question"],
                email
            )

            st.subheader("🧠 Final Answer")
            st.write(result.get("final_answer"))

            st.subheader("📧 Email Body")
            st.write(result.get("email_body"))

            st.subheader("📡 Status")
            st.success(result.get("status"))

        except Exception as e:
            st.error(f"Webhook error: {e}")


# ── Footer ──────────────────────────────────────────────
st.markdown("""
---
Contract Risk Detector · Gemini 2.0 Flash · n8n Automation
""")
