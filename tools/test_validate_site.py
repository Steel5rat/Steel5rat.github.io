#!/usr/bin/env python3

import unittest
from pathlib import Path

from tools.validate_site import REPOSITORY_ROOT, SITE_ROOT, SiteParser, normalize, resolve_local, validate_policy_dates


class SiteValidatorTest(unittest.TestCase):
    def test_parser_collects_nested_visible_anchor_text(self) -> None:
        parser = SiteParser()
        parser.feed('<main id="content"><h1>Policy</h1><a href="privacy/"><strong>Privacy</strong> policy</a></main>')
        parser.close()

        self.assertEqual(["Policy"], parser.h1s)
        self.assertEqual([("privacy/", "Privacy policy")], parser.anchors)
        self.assertIn("content", parser.ids)

    def test_project_relative_directory_route_resolves_to_index(self) -> None:
        landing = SITE_ROOT / "index.html"
        privacy = SITE_ROOT / "privacy" / "index.html"

        self.assertEqual(privacy.resolve(), resolve_local(landing, "privacy/"))
        self.assertEqual(landing.resolve(), resolve_local(privacy, "../"))

    def test_whitespace_normalization_preserves_copy(self) -> None:
        self.assertEqual("Cudouna Rubanau OÜ", normalize(" Cudouna\n  Rubanau OÜ "))

    def test_repository_root_is_the_script_parent_repository(self) -> None:
        self.assertEqual(Path(__file__).resolve().parents[1], REPOSITORY_ROOT)

    def test_policy_dates_allow_publication_on_a_later_day(self) -> None:
        parser = SiteParser()
        parser.feed("<dl><dt>Effective date</dt><dd>October 20, 2026</dd>"
                    "<dt>Last updated</dt><dd>October 21, 2026</dd></dl>")
        parser.close()
        errors: list[str] = []

        validate_policy_dates(parser, errors)

        self.assertEqual([], errors)

    def test_policy_dates_reject_reversed_order(self) -> None:
        parser = SiteParser()
        parser.feed("<dl><dt>Effective date</dt><dd>October 21, 2026</dd>"
                    "<dt>Last updated</dt><dd>October 20, 2026</dd></dl>")
        parser.close()
        errors: list[str] = []

        validate_policy_dates(parser, errors)

        self.assertIn("site/privacy/index.html: last-updated date precedes effective date", errors)


if __name__ == "__main__":
    unittest.main()
