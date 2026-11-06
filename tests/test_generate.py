import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import generate


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.category_dir = Path(self.temp_dir.name) / "Sorted Channels"
        self.category_dir.mkdir()
        (self.category_dir / "news.txt").write_text(
            '"Alpha News" 1\nAlpha\nhttps://example.com/alpha.png\n'
            '"Beta News" 2\nBeta\nhttps://example.com/beta.png\n',
            encoding="utf-8",
        )
        self.categories = generate.load_category_files(self.category_dir)
        self.generated_at = datetime(2026, 11, 6, 0, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_generation_returns_complete_mapping_without_writing(self):
        catalogs = {
            1: [
                {"name": "Alpha News", "id": "101", "group": "News"},
            ],
            2: [
                {"name": "Beta News", "id": "202", "group": "News"},
            ],
        }

        outputs = generate.generate_outputs(
            catalogs,
            self.categories,
            generated_at=self.generated_at,
            output_dir=Path("Output"),
        )

        self.assertEqual(
            set(outputs),
            {
                "Output/channels.json",
                "Output/channels_server_2.json",
                "Output/news.txt",
            },
        )
        first = json.loads(outputs["Output/channels.json"])
        second = json.loads(outputs["Output/channels_server_2.json"])
        self.assertEqual(first["channels"][0]["id"], "101")
        self.assertEqual(second["channels"][0]["id"], "202")
        self.assertIn("2026-11-06T05:30:00+05:30", first["updated_at"])
        self.assertIn("https://rkdy-linkgen.wasmer.app/play.php?id=101", outputs["Output/news.txt"])
        self.assertIn("Beta", outputs["Output/news.txt"])

    def test_preferred_server_falls_back_to_other_server(self):
        catalogs = {
            1: [{"name": "Beta News", "id": "222", "group": "News"}],
            2: [],
        }
        outputs = generate.generate_outputs(
            catalogs,
            self.categories,
            generated_at=self.generated_at,
        )
        self.assertIn("https://rkdy-linkgen.wasmer.app/play.php?id=222", outputs["Output/news.txt"])

    def test_missing_server_catalog_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing server"):
            generate.generate_outputs({1: []}, self.categories)

    def test_duplicate_matching_catalog_records_are_rejected(self):
        catalog = [
            {"name": "Alpha News", "id": "101"},
            {"name": "Alpha News", "id": "102"},
        ]
        with self.assertRaisesRegex(RuntimeError, "Duplicate configured channel"):
            generate.find_targets(catalog, self.categories)

    def test_invalid_catalog_id_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "invalid catalog ID"):
            generate.find_targets(
                [{"name": "Alpha News", "id": "bad id"}],
                self.categories,
            )

    def test_invalid_category_triplet_is_rejected(self):
        (self.category_dir / "broken.txt").write_text(
            '"Broken" 1\nOnly two lines\n',
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "three non-empty lines"):
            generate.load_category_files(self.category_dir)


if __name__ == "__main__":
    unittest.main()
