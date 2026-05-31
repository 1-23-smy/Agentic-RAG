import streamlit as st
import requests
import time

st.set_page_config(page_title="Universal Agentic RAG", page_icon="🧠", layout="centered")

API_BASE_URL = "http://127.0.0.1:8000"

st.title("🧠 Universal Agentic RAG System")
st.markdown("Ask deep, complex questions spanning across massive documents. The active Agent will autonomously route requests between **Qdrant** (Vector Search) and **Neo4j** (Graph Search) to synthesize an accurate, zero-hallucination response with deterministic citations.")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []
if "active_ingestion" not in st.session_state:
    st.session_state.active_ingestion = None

def poll_active_ingestion():
    active_ingestion = st.session_state.active_ingestion
    if not active_ingestion:
        return

    task_id = active_ingestion["task_id"]
    filename = active_ingestion["filename"]

    try:
        res = requests.get(f"{API_BASE_URL}/ingest/status/{task_id}", timeout=10)
        if res.status_code != 200:
            st.error(f"Could not check ingestion status for '{filename}'. API Error {res.status_code}: {res.text}")
            return

        status_payload = res.json()
        status = status_payload.get("status")
        message = status_payload.get("message", "Ingestion status is unavailable.")

        if status == "SUCCESS":
            st.toast("Ingestion complete. You can now ask questions about this document.")
            st.session_state.active_ingestion = None
        elif status == "FAILURE":
            error_detail = status_payload.get("error")
            if error_detail:
                st.error(f"{message} Details: {error_detail}")
            else:
                st.error(message)
            st.session_state.active_ingestion = None
        else:
            st.info(f"{message} File: {filename}")
            time.sleep(3)
            st.rerun()
    except requests.exceptions.ConnectionError:
        st.error("Failed to connect to the backend while checking ingestion status. Is the FastAPI server running on port 8000?")
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to check ingestion status: {e}")

st.subheader("Upload a PDF")
uploaded_pdf = st.file_uploader("Choose one PDF to ingest", type=["pdf"], accept_multiple_files=False)
upload_disabled = uploaded_pdf is None or st.session_state.active_ingestion is not None

if st.button("Upload PDF", disabled=upload_disabled):
    try:
        files = {
            "file": (
                uploaded_pdf.name,
                uploaded_pdf.getvalue(),
                "application/pdf",
            )
        }
        res = requests.post(f"{API_BASE_URL}/ingest/upload", files=files, timeout=30)

        if res.status_code == 200:
            payload = res.json()
            st.session_state.active_ingestion = {
                "task_id": payload["task_id"],
                "filename": payload["filename"],
            }
            st.success("PDF uploaded. Ingestion has started in the background.")
            st.rerun()
        else:
            st.error(f"Upload failed. API Error {res.status_code}: {res.text}")
    except requests.exceptions.ConnectionError:
        st.error("Failed to connect to the backend for upload. Is the FastAPI server running on port 8000?")
    except requests.exceptions.RequestException as e:
        st.error(f"Upload failed: {e}")

poll_active_ingestion()

st.divider()

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# React to user input
if prompt := st.chat_input("Ask a complex question about your documents..."):
    # Display user message in chat message container
    st.chat_message("user").markdown(prompt)
    
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Display assistant response in chat message container
    with st.chat_message("assistant"):
        with st.spinner("Agent is retrieving and reasoning (this may take up to 10 seconds)..."):
            try:
                # Ping the FastAPI endpoint
                res = requests.post(
                    "http://127.0.0.1:8000/chat", 
                    json={"query": prompt}
                )
                
                if res.status_code == 200:
                    answer = res.json().get("answer", "No answer provided.")
                    st.markdown(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                else:
                    error_msg = f"API Error {res.status_code}: {res.text}"
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})
                    
            except requests.exceptions.ConnectionError:
                st.error("Failed to connect to the backend. Is the FastAPI server running on port 8000?")
