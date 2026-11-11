#!/usr/bin/env python3

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tools import validate_site

from tools.validate_site import REPOSITORY_ROOT, SITE_ROOT, SiteParser, normalize, resolve_local, validate_policy_dates


class SiteValidatorTest(unittest.TestCase):
    def test_source_hygiene_keeps_org_checks_and_allows_built_hac_assets(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory) / "site"
            root.mkdir()
            css = root / "styles.css"
            css.write_text("body { color: white; }", encoding="utf-8")
            landing = root / "index.html"
            landing.write_text("<h1>Organization</h1>", encoding="utf-8")
            app = root / "hac"
            app.mkdir()
            (app / "icon.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            (app / "app.js").write_text('const placeholder = "http://www.w3.org/2000/svg";', encoding="utf-8")
            with patch.object(validate_site, "SITE_ROOT", root), \
                    patch.object(validate_site, "REPOSITORY_ROOT", root.parent), \
                    patch.object(validate_site, "CSS_PATH", css):
                errors: list[str] = []
                validate_site.validate_source_hygiene(errors)
                self.assertEqual([], errors)
                landing.write_text("TODO http://example.com", encoding="utf-8")
                validate_site.validate_source_hygiene(errors)
                self.assertTrue(any("prohibited placeholder text" in error for error in errors))
                self.assertTrue(any("insecure URL" in error for error in errors))

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
