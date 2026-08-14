"""
brain.py — Demeter's core with RAG + conversation memory.
Retrieves relevant chunks from the MoFA knowledge base (demeter.db) for real
questions, keeps track of recent conversation for context, and responds
naturally to greetings, closings, and acknowledgements.
"""

import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import sqlite3
import json
import requests
import numpy as np
from sentence_transformers import SentenceTransformer

# --- Config ---
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.2"
DB_FILE = "demeter.db"
TOP_K = 3
MAX_HISTORY_TURNS = 5

# --- Load embedding model once ---
print("Loading embedding model...")
embedder = SentenceTransformer("all-MiniLM-L6-v2")
print("Ready.\n")

# --- Conversation memory (in-memory, resets when program restarts) ---
conversation_history = []

# --- Small talk detection: greetings, closings, acknowledgements ---

GREETINGS = {
    "hey", "hi", "hello", "yo", "sup", "good morning", "good afternoon",
    "good evening", "how are you", "what's up", "whats up"
}

CLOSINGS = {
    "thanks", "thank you", "thanks a lot", "thank you so much",
    "that will be all", "that's all", "thats all", "that is all",
    "ok thanks", "okay thanks", "no that's all", "no thats all",
    "bye", "goodbye", "bye bye", "see you", "that's it", "thats it",
    "alright thanks", "great thanks", "ok that's all", "im done", "i'm done"
}

ACKNOWLEDGEMENTS = {"ok", "okay", "alright", "cool", "nice", "great"}


def classify_message(query):
    """Return 'greeting', 'closing', 'ack', or 'question'."""
    cleaned = query.strip().lower().strip("!?.")
    if cleaned in GREETINGS:
        return "greeting"
    if cleaned in CLOSINGS:
        return "closing"
    if cleaned in ACKNOWLEDGEMENTS:
        return "ack"
    return "question"


def retrieve(query, top_k=TOP_K):
    """Find the most relevant document chunks for a query."""
    query_emb = np.array(embedder.encode(query))

    conn = sqlite3.connect(DB_FILE)
    rows = conn.execute("SELECT source, chunk, embedding FROM knowledge").fetchall()
    conn.close()

    scored = []
    for source, chunk, emb_json in rows:
        emb = np.array(json.loads(emb_json))
        score = np.dot(query_emb, emb) / (
            np.linalg.norm(query_emb) * np.linalg.norm(emb) + 1e-8
        )
        scored.append((score, source, chunk))

    scored.sort(reverse=True, key=lambda x: x[0])
    return scored[:top_k]


def ask_llm(prompt):
    """Send a prompt to the local LLM."""
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": MODEL_NAME, "prompt": prompt, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except requests.exceptions.ConnectionError:
        return "ERROR: Can't reach Ollama. Make sure the Ollama app is running."
    except requests.exceptions.Timeout:
        return "ERROR: The model took too long to respond."
    except Exception as e:
        return f"ERROR: {e}"


def build_history_block():
    """Format recent conversation turns for context."""
    if not conversation_history:
        return ""
    lines = []
    for turn in conversation_history[-MAX_HISTORY_TURNS:]:
        lines.append(f"Farmer: {turn['question']}")
        lines.append(f"Demeter: {turn['answer']}")
    return "\n".join(lines)


def answer(query):
    """Full RAG + memory answer, aware of greetings/closings/small talk."""
    history_block = build_history_block()
    kind = classify_message(query)

    if kind == "greeting":
        prompt = f"""You are Demeter, a friendly offline agricultural assistant for Ghanaian farmers.
The farmer just greeted you: "{query}"
Reply with a short, warm greeting back, and invite them to ask a farming question. Keep it to 1-2 sentences."""
        reply = ask_llm(prompt)
        sources = []

    elif kind == "closing":
        prompt = f"""You are Demeter, a friendly offline agricultural assistant for Ghanaian farmers.
The farmer is wrapping up the conversation: "{query}"
Reply with a short, warm sign-off (1 sentence), and let them know they can come back anytime with more questions."""
        reply = ask_llm(prompt)
        sources = []

    elif kind == "ack":
        prompt = f"""You are Demeter, a friendly offline agricultural assistant for Ghanaian farmers.
The farmer just acknowledged something: "{query}"
Reply briefly and naturally (1 sentence), and ask if there's anything else they need help with."""
        reply = ask_llm(prompt)
        sources = []

    else:
        results = retrieve(query)
        context = "\n\n".join(f"[From {src}]\n{chunk}" for _, src, chunk in results)
        sources = list({src for _, src, _ in results})

        prompt = f"""You are Demeter, an offline agricultural assistant for Ghanaian farmers.
Answer the farmer's question using the information from the Ghana Ministry of Agriculture documents below,
and take the recent conversation into account so your answer fits naturally as a follow-up if relevant.
If the documents do not contain the answer, say so honestly and give general guidance, but make clear it is not from the documents.

Recent conversation:
{history_block}

--- DOCUMENTS ---
{context}
--- END DOCUMENTS ---

Farmer's question: {query}

Answer clearly and practically:"""
        reply = ask_llm(prompt)

    conversation_history.append({"question": query, "answer": reply})
    return reply, sources


if __name__ == "__main__":
    print("Demeter (with MoFA knowledge + memory). Type 'quit' to exit.\n")
    while True:
        q = input("You: ")
        if q.lower() in ("quit", "exit"):
            break
        reply, sources = answer(q)
        print(f"\nDemeter: {reply}")
        if sources:
            print(f"(Sources: {', '.join(sources)})")
        print()