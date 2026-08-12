"""
brain.py — Demeter's core with RAG + conversation memory.
Retrieves relevant chunks from the MoFA knowledge base (demeter.db) for real
questions, keeps track of recent conversation for context, and skips
document retrieval for small talk.
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
MAX_HISTORY_TURNS = 5  # how many past exchanges to remember

# --- Load embedding model once ---
print("Loading embedding model...")
embedder = SentenceTransformer("all-MiniLM-L6-v2")
print("Ready.\n")

# --- Conversation memory (in-memory, resets when program restarts) ---
conversation_history = []

# Simple small-talk detector — casual openers that don't need document lookup
SMALL_TALK = {
    "hey", "hi", "hello", "yo", "sup", "good morning", "good afternoon",
    "good evening", "thanks", "thank you", "ok", "okay", "bye", "goodbye",
    "how are you", "what's up", "whats up"
}


def is_small_talk(query):
    cleaned = query.strip().lower().strip("!?.")
    return cleaned in SMALL_TALK or len(cleaned.split()) <= 2 and cleaned in SMALL_TALK


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
    """Full RAG + memory answer."""
    history_block = build_history_block()

    if is_small_talk(query):
        # Casual message — no document retrieval, just a natural reply
        prompt = f"""You are Demeter, a friendly offline agricultural assistant for Ghanaian farmers.
Recent conversation:
{history_block}

The farmer just said: "{query}"

Reply naturally and briefly, like a helpful person would. Don't mention documents or ask an unrelated question."""
        reply = ask_llm(prompt)
        sources = []
    else:
        results = retrieve(query)
        context = "\n\n".join(f"[From {src}]\n{chunk}" for _, src, chunk in results)
        sources = list({src for _, src, _ in results})

        prompt = f"""You are Demeter, an offline agricultural assistant for Ghanaian farmers.
Answer the farmer's question using the information from the Ghana Ministry of Agriculture documents below,
and take the recent conversation into account so your answer fits naturally as a follow-up if relevant.
If the documents do not contain the answer, say so honestly and give general guidance, but make clear it is not from the documents.Recent conversation:
{history_block}

--- DOCUMENTS ---
{context}
--- END DOCUMENTS ---

Farmer's question: {query}

Answer clearly and practically:"""
        reply = ask_llm(prompt)

    # Save this turn to memory
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