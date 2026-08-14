"""
app.py — Demeter desktop application server.
Serves the UI and exposes API endpoints that connect to brain.py (RAG + LLM).
Run this, then open http://localhost:5000 (or launch via desktop.py for a
native window instead of a browser tab).
"""

import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import json
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, jsonify

import brain  # your existing brain.py — RAG + LLM logic lives there

app = Flask(__name__)

PROFILE_DB = "demeter_profile.json"


# ---------- Simple local profile storage (placeholder until SQLite profile table exists) ----------

def load_profile():
    if os.path.exists(PROFILE_DB):
        with open(PROFILE_DB, "r") as f:
            return json.load(f)
    return {
        "name": "",
        "location": "",
        "crops": [],
        "phone": ""
    }


def save_profile(data):
    with open(PROFILE_DB, "w") as f:
        json.dump(data, f, indent=2)


# ---------- Placeholder news content (swap for real MoFA feed later) ----------

PLACEHOLDER_NEWS = [
    {
        "tag": "Planting Alert",
        "title": "Maize planting window opens in Northern Region",
        "summary": "Farmers in the Northern Region can begin planting maize as seasonal rains stabilize. Ensure soil moisture is adequate before sowing.",
        "date": "Aug 10, 2026"
    },
    {
        "tag": "Market Prices",
        "title": "Cassava prices rise 8% in Kumasi markets",
        "summary": "Wholesale cassava prices have increased across major Ashanti Region markets this week, driven by strong demand from processors.",
        "date": "Aug 9, 2026"
    },
    {
        "tag": "Pest Watch",
        "title": "Fall armyworm activity reported in Bono East",
        "summary": "Extension officers are advising early scouting and approved biopesticide use for maize farmers in affected districts.",
        "date": "Aug 7, 2026"
    },
    {
        "tag": "Subsidy",
        "title": "Fertilizer subsidy applications open for 2026 season",
        "summary": "The Ministry of Food and Agriculture has opened applications for subsidized fertilizer under the Planting for Food and Jobs program.",
        "date": "Aug 5, 2026"
    },
]


# ---------- Routes: pages ----------

@app.route("/")
def home():
    return render_template("index.html", active="home", news=PLACEHOLDER_NEWS)


@app.route("/chat")
def chat():
    return render_template("chat.html", active="chat")


@app.route("/profile")
def profile():
    return render_template("profile.html", active="profile", profile=load_profile())


@app.route("/settings")
def settings():
    return render_template("settings.html", active="settings")


# ---------- Routes: API ----------

@app.route("/api/ask", methods=["POST"])
def api_ask():
    data = request.get_json(force=True)
    query = (data.get("message") or "").strip()
    if not query:
        return jsonify({"error": "No message provided"}), 400

    reply, sources = brain.answer(query)
    return jsonify({
        "reply": reply,
        "sources": sources,
        "timestamp": datetime.now().strftime("%H:%M")
    })


@app.route("/api/profile", methods=["POST"])
def api_save_profile():
    data = request.get_json(force=True)
    profile_data = {
        "name": data.get("name", ""),
        "location": data.get("location", ""),
        "crops": data.get("crops", []),
        "phone": data.get("phone", "")
    }
    save_profile(profile_data)
    return jsonify({"status": "saved"})


if __name__ == "__main__":
    print("=" * 50)
    print("  Demeter is starting...")
    print("  Open http://localhost:5000 in your browser")
    print("  (Make sure the Ollama app is running)")
    print("=" * 50)
    app.run(debug=True, port=5000)
