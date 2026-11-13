import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import generate


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.category_dir = self.root / "Sorted Channels"
        self.output_dir = self.root / "Output"
        self.category_dir.mkdir()
        self.output_dir.mkdir()
        self.category_patch = patch.object(generate, "CATEGORY_DIR", self.category_dir)
        self.output_patch = patch.object(generate, "OUTPUT_DIR", self.output_dir)
        self.category_patch.start()
        self.output_patch.start()
        self.addCleanup(self.category_patch.stop)
        self.addCleanup(self.output_patch.stop)
        self.addCleanup(self.temp_dir.cleanup)

    def write_category(self, name="drama", entries=None):
        entries = entries or [
            ('"CHANNEL ONE" 1', "Channel One", "https://example.com/logo.png")
        ]
        content = "\n\n".join("\n".join(entry) for entry in entries) + "\n"
        (self.category_dir / f"{name}.txt").write_text(content, encoding="utf-8")

    def test_normalize_name_collapses_whitespace_and_case(self):
        self.assertEqual(generate.normalize_name("  Channel   One "), "CHANNEL ONE")

    def test_load_category_files_rejects_duplicate_catalog_keys(self):
        self.write_category(entries=[
            ('"CHANNEL ONE" 1', "Channel One", "https://example.com/1.png"),
            ('" channel   one " 2', "Channel Two", "https://example.com/2.png"),
        ])
        with self.assertRaisesRegex(ValueError, "Duplicate configured channel key"):
            generate.load_category_files()

    def test_load_category_files_rejects_duplicate_display_names(self):
        self.write_category(entries=[
            ('"CHANNEL ONE" 1', "Same Name", "https://example.com/1.png"),
            ('"CHANNEL TWO" 2', " same   name ", "https://example.com/2.png"),
        ])
        with self.assertRaisesRegex(ValueError, "Duplicate configured display name"):
            generate.load_category_files()

    def test_load_category_files_requires_triplets(self):
        (self.category_dir / "broken.txt").write_text(
            '"CHANNEL ONE" 1\nChannel One\n', encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "three non-empty lines"):
            generate.load_category_files()

    def test_missing_assigned_channel_aborts_generation(self):
        self.write_category()
        with self.assertRaisesRegex(RuntimeError, "Refusing to overwrite"):
            generate.ensure_all_configured_channels_found({1: []})

    def test_category_playlist_uses_assigned_server(self):
        self.write_category()
        channel = {"name": "CHANNEL ONE", "id": "abc123"}
        targets = {1: [("CHANNEL ONE", channel, {"name": "Channel One", "logo": "https://example.com/logo.png"})]}
        playlist = generate.build_category_playlists(targets)[self.output_dir / "drama.txt"]
        self.assertIn("Channel One\nhttps://example.com/logo.png", playlist)
        self.assertIn("/play.php?s=1&id=abc123", playlist)

    def test_output_writer_replaces_existing_playlist(self):
        destination = self.output_dir / "drama.txt"
        destination.write_text("old playlist\n", encoding="utf-8")
        generate.write_outputs_atomically({destination: "new playlist\n"})
        self.assertEqual(destination.read_text(encoding="utf-8"), "new playlist\n")

    def test_unavailable_server_does_not_overwrite_existing_playlists(self):
        destination = self.output_dir / "drama.txt"
        destination.write_text("last known good playlist\n", encoding="utf-8")
        with patch.object(generate, "fetch_server_list", return_value=[(1, "Server 1")]):
            with patch.object(generate, "fetch_catalog", side_effect=RuntimeError("empty catalog")):
                self.assertEqual(generate.main(), 1)
        self.assertEqual(
            destination.read_text(encoding="utf-8"),
            "last known good playlist\n",
        )


if __name__ == "__main__":
    unittest.main()
