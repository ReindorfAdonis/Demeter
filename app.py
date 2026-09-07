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
import re
import sqlite3
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

import requests
from flask import Flask, render_template, request, jsonify

import brain  # your existing brain.py — RAG + LLM logic lives there

app = Flask(__name__)

PROFILE_DB = "demeter_profile.json"
NEWS_CACHE_FILE = "news_cache.json"
NEWS_URLS = [
    "https://news.google.com/rss/search?q=Ghana+agriculture+farming",
    "https://news.google.com/rss/search?q=Ghana+maize+farmers",
    "https://news.google.com/rss/search?q=Ghana+crop+market+farmers"
]


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


# ---------- Placeholder news content (fallback only if no live or cached data is available) ----------

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


def normalize_tag(title):
    text = (title or "").lower()
    if any(k in text for k in ["plant", "rain", "sowing", "planting", "season", "field"]):
        return "Planting Alert"
    if any(k in text for k in ["market", "price", "price rise", "cost", "commodity", "produce"]):
        return "Market Prices"
    if any(k in text for k in ["pest", "disease", "armyworm", "insect", "fungus", "weed"]):
        return "Pest Watch"
    if any(k in text for k in ["subsidy", "support", "grant", "fertilizer", "input"]):
        return "Subsidy"
    if any(k in text for k in ["weather", "drought", "flood", "rainfall", "irrigation"]):
        return "Weather"
    if any(k in text for k in ["livestock", "poultry", "cattle", "fish", "goat"]):
        return "Livestock"
    return "Agriculture"


def clean_news_text(value):
    text = re.sub(r"<.*?>", " ", value or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_news_feed(xml_text):
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    items = []
    for entry in root.findall(".//item")[:8]:
        title = clean_news_text(entry.findtext("title", default=""))
        summary = clean_news_text(entry.findtext("description", default=""))
        link = entry.findtext("link", default="")
        published = entry.findtext("pubDate", default="") or entry.findtext("published", default="")

        if not title:
            continue

        content = summary or "Latest Ghana agriculture update from the field."
        published_at = None
        if published:
            try:
                published_at = parsedate_to_datetime(published).astimezone(timezone.utc).isoformat()
            except (TypeError, ValueError, OverflowError):
                pass
        item = {
            "tag": normalize_tag(title),
            "title": title,
            "summary": content,
            "content": content,
            "date": published[:16] if published else datetime.now().strftime("%b %d, %Y"),
            "link": link,
            "published_at": published_at,
        }

        if published:
            try:
                item["sort_key"] = parsedate_to_datetime(published).timestamp()
            except Exception:
                item["sort_key"] = datetime.now().timestamp()
        else:
            item["sort_key"] = datetime.now().timestamp()

        items.append(item)

    items.sort(key=lambda x: x.get("sort_key", 0), reverse=True)
    for item in items:
        item.pop("sort_key", None)
    return items


def save_cached_news(news):
    save_news_cache({"articles": news, "lastSuccessfulSync": datetime.now(timezone.utc).isoformat()})


def save_news_cache(cache):
    temporary_file = f"{NEWS_CACHE_FILE}.tmp"
    with open(temporary_file, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)
    os.replace(temporary_file, NEWS_CACHE_FILE)


def load_cached_news():
    return load_news_cache()["articles"]


def load_news_cache():
    if not os.path.exists(NEWS_CACHE_FILE):
        return {"articles": [], "lastSuccessfulSync": None}
    try:
        with open(NEWS_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return {"articles": data, "lastSuccessfulSync": None}
        if isinstance(data, dict) and isinstance(data.get("articles"), list):
            return {
                "articles": data["articles"],
                "lastSuccessfulSync": data.get("lastSuccessfulSync"),
            }
    except (json.JSONDecodeError, OSError):
        pass
    return {"articles": [], "lastSuccessfulSync": None}


def article_key(item):
    return (item.get("link") or item.get("title") or "").strip().lower()


def merge_news(existing, incoming):
    merged = {}
    for item in existing + incoming:
        key = article_key(item)
        if key:
            merged[key] = item
    return sort_news_by_date(list(merged.values()))


def fetch_live_news(since=None, include_status=False):
    collected = []
    successful_requests = 0
    for url in NEWS_URLS:
        request_url = url
        if since:
            try:
                since_date = datetime.fromisoformat(since.replace("Z", "+00:00")).date()
                request_url = f"{url}+after:{since_date.isoformat()}"
            except ValueError:
                pass
        try:
            response = requests.get(request_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            successful_requests += 1
            parsed = parse_news_feed(response.text)
            if parsed:
                collected.extend(parsed)
        except Exception:
            continue

    deduped = []
    seen = set()
    for item in collected:
        key = article_key(item)
        if key and key not in seen:
            seen.add(key)
            deduped.append(item)

    if include_status:
        return deduped, successful_requests > 0
    return deduped


def sort_news_by_date(news):
    def parse_sort_value(item):
        published_at = item.get("published_at")
        if published_at:
            try:
                return datetime.fromisoformat(published_at.replace("Z", "+00:00")).timestamp()
            except (TypeError, ValueError, OverflowError):
                pass
        raw = item.get("date", "")
        try:
            return parsedate_to_datetime(raw).timestamp()
        except Exception:
            try:
                return datetime.strptime(raw, "%b %d, %Y").timestamp()
            except Exception:
                return 0

    return sorted(news, key=parse_sort_value, reverse=True)


def get_home_news():
    cache = load_news_cache()
    cached_news = cache["articles"]
    try:
        live_news, sync_succeeded = fetch_live_news(cache.get("lastSuccessfulSync"), include_status=True)
        if sync_succeeded:
            merged_news = merge_news(cached_news, live_news)
            save_news_cache({
                "articles": merged_news,
                "lastSuccessfulSync": datetime.now(timezone.utc).isoformat(),
            })
            if merged_news:
                return merged_news[:6], "live"
    except Exception:
        pass

    if cached_news:
        return sort_news_by_date(cached_news), "cached"

    return sort_news_by_date(PLACEHOLDER_NEWS), "fallback"


# ---------- Routes: pages ----------

@app.route("/")
def home():
    news, news_status = get_home_news()
    return render_template("index.html", active="home", news=news, news_status=news_status)


@app.route("/news/<int:item_id>")
def news_detail(item_id):
    news, _ = get_home_news()
    if item_id < 0 or item_id >= len(news):
        return "News item not found", 404

    item = news[item_id]
    return render_template("news_detail.html", active="home", item=item, item_id=item_id)


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
    app.run(debug=True, port=5000)
