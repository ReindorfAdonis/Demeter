import json
import os
import tempfile
import unittest
from unittest.mock import patch

import app


class NewsCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache_file = os.path.join(self.temp_dir.name, "news_cache.json")
        self.cache_patch = patch.object(app, "NEWS_CACHE_FILE", self.cache_file)
        self.cache_patch.start()

    def tearDown(self):
        self.cache_patch.stop()
        self.temp_dir.cleanup()

    @staticmethod
    def article(title, published_at):
        return {
            "title": title,
            "link": f"https://example.test/{title.lower().replace(' ', '-')}",
            "summary": title,
            "content": title,
            "tag": "Agriculture",
            "date": "Sep 11, 2026",
            "published_at": published_at,
        }

    def test_sync_merges_catch_up_articles_and_deduplicates(self):
        september_7 = self.article("September 7", "2026-09-07T12:00:00+00:00")
        app.save_news_cache({
            "articles": [september_7],
            "lastSuccessfulSync": "2026-09-07T18:00:00+00:00",
        })
        catch_up = [
            september_7,
            self.article("September 8", "2026-09-08T12:00:00+00:00"),
            self.article("September 9", "2026-09-09T12:00:00+00:00"),
            self.article("September 10", "2026-09-10T12:00:00+00:00"),
            self.article("September 11", "2026-09-11T12:00:00+00:00"),
        ]

        with patch.object(app, "fetch_live_news", return_value=(catch_up, True)):
            news, status = app.get_home_news()

        self.assertEqual(status, "live")
        self.assertEqual(len(app.load_cached_news()), 5)
        self.assertEqual(len({app.article_key(item) for item in app.load_cached_news()}), 5)
        self.assertEqual(news[0]["title"], "September 11")
        self.assertTrue(app.load_news_cache()["lastSuccessfulSync"])

    def test_offline_load_keeps_persistent_cache(self):
        cached = self.article("Cached article", "2026-09-07T12:00:00+00:00")
        app.save_news_cache({
            "articles": [cached],
            "lastSuccessfulSync": "2026-09-07T18:00:00+00:00",
        })

        with patch.object(app, "fetch_live_news", side_effect=OSError("offline")):
            news, status = app.get_home_news()

        self.assertEqual(status, "cached")
        self.assertEqual(news[0]["title"], "Cached article")
        with open(self.cache_file, encoding="utf-8") as cache_file:
            self.assertEqual(len(json.load(cache_file)["articles"]), 1)


if __name__ == "__main__":
    unittest.main()