import unittest
from unittest.mock import patch

import brain


class BrainStartupTests(unittest.TestCase):
    def test_get_embedder_handles_load_failure(self):
        with patch("brain.SentenceTransformer", side_effect=RuntimeError("model download failed")):
            result = brain.get_embedder()
        self.assertIsNone(result)

    def test_get_embedder_skips_remote_download_when_offline_and_not_cached(self):
        with patch.object(brain, "has_local_embedding_model", return_value=False), \
             patch.object(brain, "SentenceTransformer", create=True) as mock_transformer:
            result = brain.get_embedder()
        self.assertIsNone(result)
        mock_transformer.assert_not_called()

    def test_retrieve_returns_empty_when_embedder_unavailable(self):
        with patch.object(brain, "get_embedder", return_value=None):
            self.assertEqual(brain.retrieve("maize pest"), [])


if __name__ == "__main__":
    unittest.main()
