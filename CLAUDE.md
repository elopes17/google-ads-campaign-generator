# Google Ads Campaign Generator

## Current scope

This is an existing local Flask project using Python, Jinja, plain CSS, and openpyxl. The completed application includes validated intake, deterministic campaign generation for six services, an eight-sheet Excel export, local landing-page previews, an offline landing-page ZIP, optional user-provided business details, a manually verified Google Ads Editor draft package, and approved interface/accessibility polish.

Portfolio packaging adds a fixed fictional demo, public documentation, approved privacy-reviewed screenshots, repository hygiene, and a guarded release builder. The screenshots and local manual review are complete; release archives must still be created only through the allowlisted release builder.

Public-host preparation includes Gunicorn and an allowlisted `render.yaml`. Production must import `app:app`, keep Flask debug mode disabled, bind to Render's assigned `PORT`, and retain stateless in-memory behavior.

## Preservation rules

- Preserve unrelated local changes and all existing routes, fields, validation, service rules, keyword/negative lists, RSA assets, budgets, CTAs, availability logic, and export behavior.
- Keep exactly 15 unique headlines and 4 unique descriptions per selected ad group.
- Keep the Excel workbook at eight sheets in its existing order.
- Keep browser and offline landing-page behavior stateless, escaped, unpublished, and non-submitting.
- Keep Google Ads Editor exports paused and review-only. Never upload or post changes.
- User-controlled values must not choose routes, template names, service slugs, archive paths, or asset paths.
- Preserve formula-injection protection, safe filenames, fixed archive paths, and in-memory generation.
- Keep user-facing draft, unpublished-preview, unconfigured-tracking, and human-review notices.
- Keep internal milestone terminology out of user-facing templates.
- Use only the fixed fictional data in `demo_data.py` for portfolio examples and screenshots.
- Include only the files selected by the public release allowlist.
- Do not add JavaScript, a front-end framework, external APIs, AI generation, databases, accounts, sessions, payments, lead collection, or new dependencies.
- Do not initialize Git, commit, deploy, upload, or publish unless separately requested.

## Verification

Use the existing virtual environment and run the complete suite without skips:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
```

Before a release, complete the screenshot and privacy checks in `docs/screenshots/README.md`, run the manual verification documented in README.md, and inspect the release allowlist. Do not claim unperformed browser, Excel, Editor, or offline-package checks.
