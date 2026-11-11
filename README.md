# Cudouna Rubanau OÜ website

This public repository contains the static Cudouna Rubanau OÜ organization website and privacy policies for the LuckyLaunch and Halera Android apps.

- Organization website: <https://steel5rat.github.io/>
- LuckyLaunch privacy policy: <https://steel5rat.github.io/privacy/>
- Halera privacy policy: <https://steel5rat.github.io/halera/privacy/>
- Hac sailing forecast: <https://steel5rat.github.io/hac/>

The deployable files live in [`site/`](./site). The organization website and privacy policies use plain semantic HTML and CSS with no JavaScript, backend, analytics, advertising, cookies, or external runtime assets.

Hac is a separate browser app in [`site/hac/`](./site/hac), generated with `npm run build:web` in the Hac repository. It fetches forecasts from Open-Meteo and stores routes and forecasts locally in the browser. Its build and browser tests are maintained in Hac; this repository validates the organization pages and privacy policies.

## Validate locally

```bash
python3 -m unittest tools/test_validate_site.py
python3 tools/validate_site.py
python3 -m http.server 8000 --directory site
```

The [Pages workflow](./.github/workflows/pages.yml) validates and deploys `site/` after changes reach `main`.
