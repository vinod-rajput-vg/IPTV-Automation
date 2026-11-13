import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import generate


class CategoryPlaylistFallbackTests(unittest.TestCase):
    def setUp(self):
        self.channel_metadata = {
            "name": "Example Channel",
            "logo": "https://example.com/logo.png",
        }
        self.category_entry = {
            "key": "EXAMPLE CHANNEL",
            "server": 1,
            "name": "Example Channel",
            "logo": "https://example.com/logo.png",
        }
        self.server_targets = {
            1: [("EXAMPLE CHANNEL", {"id": "preferred"}, self.channel_metadata)],
            2: [("EXAMPLE CHANNEL", {"id": "fallback"}, self.channel_metadata)],
        }
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.output_dir = Path(self.temp_dir.name)

    def build_playlist(self, validated_urls):
        with (
            patch.object(generate, "load_category_files", return_value={"news": [self.category_entry]}),
            patch.object(generate, "OUTPUT_DIR", self.output_dir),
        ):
            return generate.build_category_playlists(self.server_targets, validated_urls)

    def test_uses_validated_fallback_when_preferred_server_is_unavailable(self):
        fallback_url = generate.build_stream_url("fallback")
        playlist = self.build_playlist({fallback_url})
        self.assertIn(fallback_url, playlist[self.output_dir / "news.txt"])
        self.assertNotIn(generate.build_stream_url("preferred"), playlist[self.output_dir / "news.txt"])

    def test_prefers_configured_server_when_it_is_valid(self):
        preferred_url = generate.build_stream_url("preferred")
        fallback_url = generate.build_stream_url("fallback")
        playlist = self.build_playlist({preferred_url, fallback_url})
        self.assertIn(preferred_url, playlist[self.output_dir / "news.txt"])
        self.assertNotIn(fallback_url, playlist[self.output_dir / "news.txt"])

    def test_keeps_preferred_server_when_no_stream_validates(self):
        preferred_url = generate.build_stream_url("preferred")
        playlist = self.build_playlist(set())
        self.assertIn(preferred_url, playlist[self.output_dir / "news.txt"])


if __name__ == "__main__":
    unittest.main()
