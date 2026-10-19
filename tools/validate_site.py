#!/usr/bin/env python3
"""Validate the LuckyLaunch static site and current privacy disclosure."""

from __future__ import annotations

import re
import sys
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = REPOSITORY_ROOT / "site"
CSS_PATH = SITE_ROOT / "styles.css"
WORKFLOW_PATH = REPOSITORY_ROOT / ".github" / "workflows" / "pages.yml"
EMAIL = "ivan.rubanau@gmail.com"
LEGAL_NAME = "Cudouna Rubanau OÜ"
BASE_URL = "https://steel5rat.github.io/"
ALLOWED_PRIVACY_LINK = "https://policies.google.com/privacy"
MAX_BLOCKING_BYTES = 50 * 1024


def normalize(value: str) -> str:
    return " ".join(value.split())


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.start_tags: list[tuple[str, dict[str, str | None]]] = []
        self.ids: set[str] = set()
        self.text_parts: list[str] = []
        self.titles: list[str] = []
        self.h1s: list[str] = []
        self.h2s: list[str] = []
        self.paragraphs: list[str] = []
        self.definition_terms: list[str] = []
        self.definition_values: list[str] = []
        self.anchors: list[tuple[str, str]] = []
        self._capture: list[tuple[str, list[str], str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        self.start_tags.append((tag, attr_map))
        element_id = attr_map.get("id")
        if element_id:
            self.ids.add(element_id)
        if tag in {"title", "h1", "h2", "p", "dt", "dd"}:
            self._capture.append((tag, [], None))
        elif tag == "a":
            self._capture.append((tag, [], attr_map.get("href")))

    def handle_endtag(self, tag: str) -> None:
        if not self._capture or self._capture[-1][0] != tag:
            return
        captured_tag, parts, href = self._capture.pop()
        value = normalize("".join(parts))
        if captured_tag == "title":
            self.titles.append(value)
        elif captured_tag == "h1":
            self.h1s.append(value)
        elif captured_tag == "h2":
            self.h2s.append(value)
        elif captured_tag == "p":
            self.paragraphs.append(value)
        elif captured_tag == "dt":
            self.definition_terms.append(value)
        elif captured_tag == "dd":
            self.definition_values.append(value)
        elif captured_tag == "a":
            self.anchors.append((href or "", value))

    def handle_data(self, data: str) -> None:
        self.text_parts.append(data)
        for _, parts, _ in self._capture:
            parts.append(data)

    @property
    def text(self) -> str:
        return normalize(" ".join(self.text_parts))


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def resolve_local(page_path: Path, href: str) -> Path:
    path = unquote(urlsplit(href).path)
    target = (page_path.parent / path).resolve()
    if href.endswith("/") or target.is_dir():
        target /= "index.html"
    return target


def validate_common(page_path: Path, parser: SiteParser, errors: list[str]) -> None:
    relative = page_path.relative_to(REPOSITORY_ROOT)
    html_tags = [attrs for tag, attrs in parser.start_tags if tag == "html"]
    if len(html_tags) != 1 or html_tags[0].get("lang") != "en":
        fail(errors, f"{relative}: expected one <html lang=\"en\">")

    if len(parser.titles) != 1 or not parser.titles[0]:
        fail(errors, f"{relative}: expected one non-empty title")
    if len(parser.h1s) != 1:
        fail(errors, f"{relative}: expected exactly one h1")

    meta = [attrs for tag, attrs in parser.start_tags if tag == "meta"]
    if not any((attrs.get("charset") or "").lower() == "utf-8" for attrs in meta):
        fail(errors, f"{relative}: missing UTF-8 charset")
    if not any(attrs.get("name") == "viewport" for attrs in meta):
        fail(errors, f"{relative}: missing viewport metadata")
    descriptions = [attrs.get("content") for attrs in meta if attrs.get("name") == "description"]
    if len(descriptions) != 1 or not descriptions[0]:
        fail(errors, f"{relative}: expected one meta description")

    policies = [
        attrs.get("content") or ""
        for attrs in meta
        if (attrs.get("http-equiv") or "").lower() == "content-security-policy"
    ]
    required_directives = {
        "default-src 'none'",
        "style-src 'self'",
        "img-src 'self' data:",
        "script-src 'none'",
        "connect-src 'none'",
        "form-action 'none'",
        "base-uri 'none'",
        "upgrade-insecure-requests",
    }
    if len(policies) != 1 or not required_directives.issubset(set(policies[0].split("; "))):
        fail(errors, f"{relative}: restrictive Content Security Policy is incomplete")

    semantic_tags = {tag for tag, _ in parser.start_tags}
    for required in {"header", "nav", "main", "section", "address", "footer"}:
        if required not in semantic_tags:
            fail(errors, f"{relative}: missing semantic <{required}> element")

    stylesheet_links = [
        attrs
        for tag, attrs in parser.start_tags
        if tag == "link" and attrs.get("rel") == "stylesheet"
    ]
    if len(stylesheet_links) != 1:
        fail(errors, f"{relative}: expected exactly one stylesheet request")
    icon_links = [
        attrs
        for tag, attrs in parser.start_tags
        if tag == "link" and attrs.get("rel") == "icon"
    ]
    if len(icon_links) != 1 or not (icon_links[0].get("href") or "").startswith("data:image/svg+xml,"):
        fail(errors, f"{relative}: expected one inline favicon to prevent an extra browser request")
    if any(tag in {"script", "form", "iframe"} for tag, _ in parser.start_tags):
        fail(errors, f"{relative}: scripts, forms, and frames are prohibited")
    if any("src" in attrs for _, attrs in parser.start_tags):
        fail(errors, f"{relative}: runtime assets other than the shared stylesheet are prohibited")
    for tag, attrs in parser.start_tags:
        if "style" in attrs or any(name.lower().startswith("on") for name in attrs):
            fail(errors, f"{relative}: inline styles and event handlers are prohibited on <{tag}>")

    canonical = [
        attrs.get("href")
        for tag, attrs in parser.start_tags
        if tag == "link" and attrs.get("rel") == "canonical"
    ]
    if len(canonical) != 1 or not (canonical[0] or "").startswith(BASE_URL):
        fail(errors, f"{relative}: canonical URL must use the production Pages base URL")

    for tag, attrs in parser.start_tags:
        for attribute in ("href", "src"):
            value = attrs.get(attribute)
            if value is None:
                continue
            if not value.strip():
                fail(errors, f"{relative}: <{tag}> has an empty {attribute}")
                continue
            if value.startswith("http://") or value.startswith("//"):
                fail(errors, f"{relative}: insecure or protocol-relative URL: {value}")
            if value.startswith("https://"):
                if not ((tag == "link" and attrs.get("rel") == "canonical") or
                        (page_path == SITE_ROOT / "privacy" / "index.html" and tag == "a" and value == ALLOWED_PRIVACY_LINK)):
                    fail(errors, f"{relative}: external runtime/navigation URL is prohibited: {value}")
                continue
            if value.startswith("data:"):
                if not (tag == "link" and attrs.get("rel") == "icon" and value.startswith("data:image/svg+xml,")):
                    fail(errors, f"{relative}: unexpected data URL: {value[:40]}")
                continue
            if value.startswith("mailto:"):
                if value != f"mailto:{EMAIL}":
                    fail(errors, f"{relative}: unexpected email target: {value}")
                continue
            if value.startswith("#"):
                if value[1:] not in parser.ids:
                    fail(errors, f"{relative}: unresolved fragment: {value}")
                continue
            target = resolve_local(page_path, value)
            try:
                target.relative_to(SITE_ROOT.resolve())
            except ValueError:
                fail(errors, f"{relative}: local URL escapes the site root: {value}")
                continue
            if not target.is_file():
                fail(errors, f"{relative}: unresolved local URL: {value}")

    if LEGAL_NAME not in parser.text:
        fail(errors, f"{relative}: legal name is missing")
    if EMAIL not in parser.text or (f"mailto:{EMAIL}", EMAIL) not in parser.anchors:
        fail(errors, f"{relative}: visible working contact email is missing")
    if page_path.stat().st_size + CSS_PATH.stat().st_size > MAX_BLOCKING_BYTES:
        fail(errors, f"{relative}: HTML plus blocking CSS exceeds 50 KiB")


def validate_landing(parser: SiteParser, errors: list[str]) -> None:
    expected_profile = (
        "Cudouna Rubanau OÜ is a software engineering company that builds and maintains "
        "software products."
    )
    if parser.titles != ["Cudouna Rubanau OÜ — Software engineering"]:
        fail(errors, "site/index.html: incorrect title")
    if parser.h1s != [LEGAL_NAME]:
        fail(errors, "site/index.html: incorrect h1")
    if parser.paragraphs.count(expected_profile) != 1:
        fail(errors, "site/index.html: company profile must appear exactly once with approved copy")
    privacy_links = [href for href, text in parser.anchors if text == "Privacy Policy for LuckyLaunch"]
    if not privacy_links or any(href != "privacy/" for href in privacy_links):
        fail(errors, "site/index.html: privacy links must target the project-relative privacy route")


def validate_policy_dates(parser: SiteParser, errors: list[str]) -> None:
    if parser.definition_terms != ["Effective date", "Last updated"] or len(parser.definition_values) != 2:
        fail(errors, "site/privacy/index.html: effective and last-updated dates must both be present")
        return
    try:
        effective, updated = [datetime.strptime(value, "%B %d, %Y").date() for value in parser.definition_values]
    except ValueError:
        fail(errors, "site/privacy/index.html: policy dates must use Month day, year format")
        return
    if updated < effective:
        fail(errors, "site/privacy/index.html: last-updated date precedes effective date")


def validate_privacy(parser: SiteParser, errors: list[str]) -> None:
    expected_sections = [
        "Who we are",
        "Scope",
        "Data LuckyLaunch processes",
        "Personal information",
        "Advertising",
        "Payments",
        "Data sharing",
        "Retention and deletion",
        "Security",
        "Children's privacy",
        "Changes to this policy",
        "Contact",
    ]
    if parser.h1s != ["Privacy Policy for LuckyLaunch"]:
        fail(errors, "site/privacy/index.html: incorrect h1")
    if parser.h2s != expected_sections:
        fail(errors, "site/privacy/index.html: policy sections are missing or out of order")
    validate_policy_dates(parser, errors)

    required_paragraphs = [
        "History stays on your device. Sharing your app choices and chances is optional.",
        "Consented analytics uses a pseudonymous app-instance identifier. Depending on applicable law, this can be personal data.",
        "LuckyLaunch shows no ads and does not use Analytics data for advertising.",
        "LuckyLaunch processes no in-app payments or purchases.",
    ]
    for paragraph in required_paragraphs:
        if paragraph not in parser.paragraphs:
            fail(errors, f"site/privacy/index.html: missing exact required clause: {paragraph}")
    required_phrases = [
        "time of a successful dispatch",
        "at most the newest 50 records",
        "up to 30 rolling days",
        "Clear history",
        "uninstalling LuckyLaunch",
        "Android's application sandbox",
        "No storage or transmission method can be promised to be absolutely secure",
        "cloud synchronization",
        "crash-reporting service",
        "ordinary web request data",
        "sets no cookies",
        "same URL with a revised last-updated date",
        "This voluntary contact is separate from LuckyLaunch app data",
        "Google Analytics for Firebase",
        "Share usage analytics",
        "two months",
        "standard aggregate reports may remain longer",
        "app-instance identifier",
        "exact configured chance",
        "package names of the apps in your current saved mix and later saved changes",
        "Package names can reveal the kinds of apps you use.",
        "does not immediately delete data already sent",
    ]
    for phrase in required_phrases:
        if phrase not in parser.text:
            fail(errors, f"site/privacy/index.html: missing disclosure: {phrase}")
    if not any(href == "../" and text == "Organization website" for href, text in parser.anchors):
        fail(errors, "site/privacy/index.html: missing link back to the organization website")
    if (ALLOWED_PRIVACY_LINK, "Google's Privacy Policy") not in parser.anchors:
        fail(errors, "site/privacy/index.html: missing Google privacy link")
    obsolete_claims = [
        "collects zero personal information",
        "never sent to Cudouna Rubanau OÜ or a third-party analytics service",
        "no user account, cloud synchronization, backend service, remote analytics",
        "do not send local mix and History records",
    ]
    for claim in obsolete_claims:
        if claim.lower() in parser.text.lower():
            fail(errors, f"site/privacy/index.html: obsolete no-analytics claim: {claim}")


def validate_source_hygiene(errors: list[str]) -> None:
    forbidden = re.compile(
        r"\b(?:TODO|TBD)\b|lorem ipsum|example\.(?:com|org|net)|placeholder|(?:verification|site)[-_ ]token",
        re.IGNORECASE,
    )
    for path in sorted(SITE_ROOT.rglob("*")):
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        match = forbidden.search(content)
        if match:
            fail(errors, f"{path.relative_to(REPOSITORY_ROOT)}: prohibited placeholder text: {match.group(0)!r}")
        if "http://" in content:
            fail(errors, f"{path.relative_to(REPOSITORY_ROOT)}: insecure URL found")
    css = CSS_PATH.read_text(encoding="utf-8")
    if re.search(r"@import\b|url\s*\(", css, re.IGNORECASE):
        fail(errors, "site/styles.css: external or additional CSS assets are prohibited")


def validate_workflow(errors: list[str]) -> None:
    if not WORKFLOW_PATH.is_file():
        fail(errors, ".github/workflows/pages.yml: deployment workflow is missing")
        return
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    required = [
        "python3 tools/validate_site.py",
        "actions/checkout@v7",
        "actions/configure-pages@v6",
        "actions/upload-pages-artifact@v5",
        "actions/deploy-pages@v5",
        "path: site",
        "pages: write",
        "id-token: write",
        "name: github-pages",
    ]
    for value in required:
        if value not in workflow:
            fail(errors, f".github/workflows/pages.yml: missing deployment contract: {value}")


def main() -> int:
    errors: list[str] = []
    required_files = [SITE_ROOT / "index.html", SITE_ROOT / "privacy" / "index.html", CSS_PATH, SITE_ROOT / ".nojekyll"]
    for path in required_files:
        if not path.is_file():
            fail(errors, f"{path.relative_to(REPOSITORY_ROOT)}: required file is missing")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    parsed: dict[Path, SiteParser] = {}
    for page_path in required_files[:2]:
        parser = SiteParser()
        parser.feed(page_path.read_text(encoding="utf-8"))
        parser.close()
        parsed[page_path] = parser
        validate_common(page_path, parser, errors)

    validate_landing(parsed[SITE_ROOT / "index.html"], errors)
    validate_privacy(parsed[SITE_ROOT / "privacy" / "index.html"], errors)
    if len({parser.titles[0] for parser in parsed.values() if parser.titles}) != len(parsed):
        fail(errors, "site pages must have unique titles")
    validate_source_hygiene(errors)
    validate_workflow(errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    root_bytes = (SITE_ROOT / "index.html").stat().st_size + CSS_PATH.stat().st_size
    privacy_bytes = (SITE_ROOT / "privacy" / "index.html").stat().st_size + CSS_PATH.stat().st_size
    print("LuckyLaunch site contract: PASS")
    print(f"Root blocking payload: {root_bytes} bytes")
    print(f"Privacy blocking payload: {privacy_bytes} bytes")
    print("Requests per page: 2 (HTML + shared CSS)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
