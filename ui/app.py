import streamlit as st
import requests

st.set_page_config(page_title="Medical Agentic RAG", page_icon="🩺", layout="centered")

st.title("🩺 Agentic Medical RAG System")
st.markdown("Ask complex medical questions spanning across 3000+ pages of dense documentation. The active RAG Agent will route requests between **Qdrant** (Vector Search) and **Neo4j** (Graph Search) to synthesize an accurate response with determinisic citations.")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# React to user input
if prompt := st.chat_input("Ask a clinical or pharmaceutical question..."):
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
