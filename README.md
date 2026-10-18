# Cudouna Rubanau OÜ website

This public repository contains the static Cudouna Rubanau OÜ organization website and the LuckyLaunch Android app privacy policy.

- Organization website: <https://steel5rat.github.io/>
- LuckyLaunch privacy policy: <https://steel5rat.github.io/privacy/>

The deployable files live in [`site/`](./site). The website uses plain semantic HTML and CSS with no JavaScript, backend, analytics, advertising, cookies, or external runtime assets.

## Validate locally

```bash
python3 -m unittest tools/test_validate_site.py
python3 tools/validate_site.py
python3 -m http.server 8000 --directory site
```

The [Pages workflow](./.github/workflows/pages.yml) validates and deploys `site/` after changes reach `main`.
