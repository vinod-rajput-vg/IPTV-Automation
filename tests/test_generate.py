import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import generate


class CategoryConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.category_dir = Path(self.temp_dir.name)
        self.category_file = self.category_dir / "news.txt"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_loads_valid_category_entries(self):
        self.category_file.write_text(
            '"NEWS ONE" 1\\nNews One\\nhttps://example.com/logo.png\\n',
            encoding="utf-8",
        )
        with patch.object(generate, "CATEGORY_DIR", self.category_dir):
            categories = generate.load_category_files()
        self.assertEqual(categories["news"][0]["key"], "NEWS ONE")
        self.assertEqual(categories["news"][0]["server"], 1)

    def test_rejects_duplicate_channel_keys_across_categories(self):
        self.category_file.write_text(
            '"NEWS ONE" 1\\nNews One\\nhttps://example.com/logo.png\\n',
            encoding="utf-8",
        )
        (self.category_dir / "other.txt").write_text(
            '"news one" 2\\nNews One HD\\nhttps://example.com/other.png\\n',
            encoding="utf-8",
        )
        with patch.object(generate, "CATEGORY_DIR", self.category_dir):
            with self.assertRaisesRegex(ValueError, "Duplicate channel key"):
                generate.load_category_files()

    def test_rejects_incomplete_three_line_entry(self):
        self.category_file.write_text('"NEWS ONE" 1\\nNews One\\n', encoding="utf-8")
        with patch.object(generate, "CATEGORY_DIR", self.category_dir):
            with self.assertRaisesRegex(ValueError, "three non-empty lines"):
                generate.load_category_files()


class PlaylistValidationTests(unittest.TestCase):
    def test_uses_validated_fallback_server(self):
        with tempfile.TemporaryDirectory() as directory:
            category_dir = Path(directory)
            (category_dir / "news.txt").write_text(
                '"NEWS ONE" 1\\nNews One\\nhttps://example.com/logo.png\\n',
                encoding="utf-8",
            )
            server_targets = {
                1: [("NEWS ONE", {"id": "broken"}, {"name": "News One", "logo": "https://example.com/logo.png"})],
                2: [("NEWS ONE", {"id": "working"}, {"name": "News One", "logo": "https://example.com/logo.png"})],
            }
            valid_url = generate.build_stream_url("working")
            with patch.object(generate, "CATEGORY_DIR", category_dir):
                playlists = generate.build_category_playlists(server_targets, {valid_url})
            playlist = playlists[generate.OUTPUT_DIR / "news.txt"]
            self.assertIn("play.php?id=working", playlist)
            self.assertNotIn("play.php?id=broken", playlist)

    def test_omits_channel_when_no_server_copy_is_validated(self):
        with tempfile.TemporaryDirectory() as directory:
            category_dir = Path(directory)
            (category_dir / "news.txt").write_text(
                '"NEWS ONE" 1\\nNews One\\nhttps://example.com/logo.png\\n',
                encoding="utf-8",
            )
            server_targets = {
                1: [("NEWS ONE", {"id": "broken"}, {"name": "News One", "logo": "https://example.com/logo.png"})],
            }
            with patch.object(generate, "CATEGORY_DIR", category_dir):
                playlists = generate.build_category_playlists(server_targets, set())
            self.assertEqual(playlists[generate.OUTPUT_DIR / "news.txt"], "")


if __name__ == "__main__":
    unittest.main()
