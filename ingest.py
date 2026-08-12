"""
ingest.py — Demeter's knowledge ingestion pipeline.
Reads PDFs from the documents folder, extracts and chunks their text,
turns each chunk into an embedding, and stores everything in SQLite.
Run this once (or whenever you add new documents).
"""
import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"


import os
import sqlite3
import json
import fitz  # PyMuPDF
from sentence_transformers import SentenceTransformer

# --- Config ---
DOCS_FOLDER = "documents"
DB_FILE = "demeter.db"
CHUNK_SIZE = 500      # words per chunk
CHUNK_OVERLAP = 50    # words shared between neighbouring chunks

# --- Load the embedding model (downloads once, then works offline) ---
print("Loading embedding model (first run downloads it, please wait)...")
model = SentenceTransformer("all-MiniLM-L6-v2")
print("Model loaded.\n")


def extract_text(pdf_path):
    """Pull all text out of a single PDF."""
    doc = fitz.open(pdf_path)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text


def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Split text into overlapping word-chunks."""
    words = text.split()
    chunks = []
    step = size - overlap
    for i in range(0, len(words), step):
        chunk = " ".join(words[i:i + size])
        if chunk.strip():
            chunks.append(chunk)
    return chunks


def main():
    # Set up the database
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS knowledge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            chunk TEXT,
            embedding TEXT
        )
    """)
    # Start fresh each run so we don't get duplicates
    conn.execute("DELETE FROM knowledge")
    conn.commit()

    if not os.path.isdir(DOCS_FOLDER):
        print(f"ERROR: '{DOCS_FOLDER}' folder not found.")
        return

    pdf_files = [f for f in os.listdir(DOCS_FOLDER) if f.lower().endswith(".pdf")]
    if not pdf_files:
        print(f"No PDF files found in '{DOCS_FOLDER}'.")
        return

    print(f"Found {len(pdf_files)} PDF(s): {', '.join(pdf_files)}\n")

    total_chunks = 0
    for pdf in pdf_files:
        path = os.path.join(DOCS_FOLDER, pdf)
        print(f"Processing: {pdf}")
        try:
            text = extract_text(path)
            chunks = chunk_text(text)
            print(f"  -> {len(chunks)} chunks")

            for chunk in chunks:
                emb = model.encode(chunk).tolist()
                conn.execute(
                    "INSERT INTO knowledge (source, chunk, embedding) VALUES (?, ?, ?)",
                    (pdf, chunk, json.dumps(emb))
                )
            conn.commit()
            total_chunks += len(chunks)
        except Exception as e:
            print(f"  !! Failed on {pdf}: {e}")

    conn.close()
    print(f"\nDone. Stored {total_chunks} chunks from {len(pdf_files)} document(s) into {DB_FILE}.")


if __name__ == "__main__":
    main()