import unittest

import generate


class GeneratorTests(unittest.TestCase):
    def test_normalize_name_collapses_whitespace_and_case(self):
        self.assertEqual(
            generate.normalize_name("  Times Now   Nav Bharat "),
            "TIMES NOW NAV BHARAT",
        )

    def test_find_targets_matches_normalized_names(self):
        catalog = [
            {"name": f"  {name.lower()}  ", "id": str(index)}
            for index, name in enumerate(generate.TARGETS, start=1)
        ]

        targets = generate.find_targets(catalog)

        self.assertEqual(len(targets), len(generate.TARGETS))
        self.assertEqual(
            [target[0] for target in targets],
            list(generate.TARGETS),
        )

    def test_find_targets_rejects_duplicate_target_records(self):
        first_target = next(iter(generate.TARGETS))
        catalog = [
            {"name": name, "id": str(index)}
            for index, name in enumerate(generate.TARGETS, start=1)
        ]
        catalog.append({"name": first_target.lower(), "id": "duplicate"})

        with self.assertRaisesRegex(RuntimeError, "Duplicate target"):
            generate.find_targets(catalog)

    def test_find_targets_rejects_missing_target_records(self):
        catalog = [
            {"name": name, "id": str(index)}
            for index, name in enumerate(generate.TARGETS, start=1)
        ][1:]

        with self.assertRaisesRegex(RuntimeError, "Missing target"):
            generate.find_targets(catalog)

    def test_find_targets_rejects_blank_or_whitespace_ids(self):
        catalog = [
            {"name": name, "id": str(index)}
            for index, name in enumerate(generate.TARGETS, start=1)
        ]
        catalog[0]["id"] = "   "

        with self.assertRaisesRegex(RuntimeError, "no catalog ID"):
            generate.find_targets(catalog)

    def test_find_targets_can_select_available_targets_per_source(self):
        first_target = next(iter(generate.TARGETS))
        targets = generate.find_targets(
            [{"name": first_target, "id": "server-specific-id"}],
            require_all=False,
        )

        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0][0], first_target)
        self.assertEqual(targets[0][1]["id"], "server-specific-id")

    def test_find_targets_rejects_source_without_any_configured_target(self):
        with self.assertRaisesRegex(RuntimeError, "No configured target"):
            generate.find_targets([{"name": "unmapped channel", "id": "1"}], require_all=False)


if __name__ == "__main__":
    unittest.main()
