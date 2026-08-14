"""
desktop.py — launches Demeter as a native desktop window (not a browser tab).
Run this instead of app.py for the full desktop app experience.
"""

import threading
import webview
from app import app


def start_flask():
    app.run(port=5000, debug=False, use_reloader=False)


if __name__ == "__main__":
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()

    webview.create_window(
        "Demeter",
        "http://localhost:5000",
        width=1280,
        height=820,
        min_size=(960, 640),
        background_color="#F5F0E4",
    )
    webview.start()
