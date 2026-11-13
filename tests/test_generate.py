import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import generate


class CategoryPlaylistSelectionTests(unittest.TestCase):
    def setUp(self):
        self.metadata = {"name": "Example Channel", "logo": "https://example.com/logo.png"}
        self.entry = {
            "key": "EXAMPLE CHANNEL",
            "server": 1,
            "name": "Example Channel",
            "logo": "https://example.com/logo.png",
        }
        self.targets = {
            1: [("EXAMPLE CHANNEL", {"id": "preferred"}, self.metadata)],
            2: [("EXAMPLE CHANNEL", {"id": "fallback"}, self.metadata)],
        }
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.output_dir = Path(self.temp_dir.name)

    def test_uses_configured_server_without_stream_validation(self):
        with (
            patch.object(generate, "load_category_files", return_value={"news": [self.entry]}),
            patch.object(generate, "OUTPUT_DIR", self.output_dir),
        ):
            playlists = generate.build_category_playlists(self.targets)
        content = playlists[self.output_dir / "news.txt"]
        self.assertIn(generate.build_stream_url("preferred"), content)
        self.assertNotIn(generate.build_stream_url("fallback"), content)

    def test_full_server_json_exports_all_non_adult_channels(self):
        catalog = [
            {"name": "News One", "id": "n1", "group": "NEWS", "logo": "https://x.test/n.png"},
            {"name": "Adult Channel", "id": "a1", "group": "ADULT 18+", "logo": ""},
            {"name": "Sports One", "id": "s1", "group": "SPORTS", "logo": ""},
        ]
        result = generate.build_full_server_json(catalog, 4)
        self.assertEqual(result["total_channels"], 2)
        self.assertEqual([item["id"] for item in result["channels"]], ["n1", "s1"])
        self.assertNotIn("validation_status", result["channels"][0])


if __name__ == "__main__":
    unittest.main()
