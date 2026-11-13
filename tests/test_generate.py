import tempfile
import unittest
from pathlib import Path

import generate


class NormalizeNameTests(unittest.TestCase):
    def test_collapses_whitespace_and_normalizes_case(self):
        self.assertEqual(generate.normalize_name("  Zee   TV HD  "), "ZEE TV HD")

    def test_none_becomes_empty_string(self):
        self.assertEqual(generate.normalize_name(None), "")


class CategoryConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_dir = generate.CATEGORY_DIR
        generate.CATEGORY_DIR = Path(self.temp_dir.name)

    def tearDown(self):
        generate.CATEGORY_DIR = self.original_dir
        self.temp_dir.cleanup()

    def write_category(self, name, content):
        (generate.CATEGORY_DIR / name).write_text(content, encoding="utf-8")

    def test_loads_channel_triplets(self):
        self.write_category(
            "news.txt",
            '"NDTV INDIA" 1\nNDTV India\nhttps://example.com/logo.png\n',
        )

        categories = generate.load_category_files()

        self.assertEqual(len(categories["news"]), 1)
        self.assertEqual(categories["news"][0]["key"], "NDTV INDIA")
        self.assertEqual(categories["news"][0]["server"], 1)

    def test_rejects_incomplete_triplet(self):
        self.write_category("news.txt", '"NDTV INDIA" 1\nNDTV India\n')

        with self.assertRaisesRegex(ValueError, "three non-empty lines"):
            generate.load_category_files()

    def test_rejects_invalid_header(self):
        self.write_category(
            "news.txt",
            'NDTV INDIA 1\nNDTV India\nhttps://example.com/logo.png\n',
        )

        with self.assertRaisesRegex(ValueError, "Invalid channel header"):
            generate.load_category_files()

    def test_rejects_invalid_logo_url(self):
        self.write_category("news.txt", '"NDTV INDIA" 1\nNDTV India\nnot-a-url\n')

        with self.assertRaisesRegex(ValueError, "Invalid logo URL"):
            generate.load_category_files()

    def test_rejects_missing_category_directory(self):
        generate.CATEGORY_DIR = Path(self.temp_dir.name) / "missing"

        with self.assertRaisesRegex(RuntimeError, "Category directory not found"):
            generate.load_category_files()


class FullCatalogTests(unittest.TestCase):
    def test_skips_invalid_and_duplicate_channel_ids(self):
        catalog = [
            {"name": "News One", "id": "1", "group": "News", "logo": "logo.png"},
            {"name": "Duplicate", "id": "1"},
            {"name": "Missing ID"},
            {"name": "Bad ID", "id": "bad id"},
        ]

        result = generate.build_full_server_json(catalog, 3)

        self.assertEqual(result["total_channels"], 1)
        self.assertEqual(len(result["channels"]), 1)
        self.assertEqual(result["channels"][0]["url"],
                         "https://rkdy-linkgen.wasmer.app/play.php?s=3&id=1")

    def test_empty_catalog_is_represented_as_empty(self):
        result = generate.build_full_server_json([], 2)

        self.assertEqual(result["total_channels"], 0)
        self.assertEqual(result["channels"], [])


if __name__ == "__main__":
    unittest.main()
