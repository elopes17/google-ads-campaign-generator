# Development history

This document keeps the project’s implementation history separate from the product-facing interface and primary portfolio README.

## Foundation

The first release established the Flask intake, server-side validation, results view, six-service rules library, curated keyword and negative-keyword templates, unique responsive-search-ad assets, location formatting, CTA variants, availability controls, and cent-safe budget allocation.

## Excel export

An in-memory openpyxl export added eight ordered worksheets, numeric currency cells, formula-injection protection, safe filenames, and regenerated output from validated inputs.

## Landing-page previews

Service-specific local previews were added through one shared escaped Jinja template and an isolated stylesheet. The previews support Calls, Forms, and Both behavior, optional validated phone links, user-provided business details, explicit placeholders, and disabled request-form mockups.

An offline ZIP export reuses the same page data and template while switching to relative local navigation and assets. The package is generated in memory and stores nothing on the server.

## Business profile details

Optional phone, license, insurance, and additional-business-information fields were added with normalization, strict phone parsing, output escaping, and stateless transport through preview and export routes. Supplied details are identified as user-provided and are not independently verified.

## Google Ads Editor draft

The Editor export creates a paused proposed-change package with campaigns, ad groups, budgets, keywords, negatives, responsive search ads, and service URLs derived from a validated HTTPS origin. It includes formula-injection rejection, fixed internal paths, UTF-8 BOM/CRLF formatting, and review instructions.

Google Ads Editor 2.13.4 manually recognized the exported Search campaigns, ad groups, keywords, negatives, and responsive search ads. Campaign rows were paused and accepted `EU political ads` as `No`. Automatic acceptance was disabled, nothing was posted, and all proposed changes were rejected after verification.

## Interface and accessibility polish

The intake and results pages gained clearer hierarchy, responsive cards and grids, export summaries, table scrolling, semantic landmarks, skip navigation, and visible keyboard focus. Landing-page previews received minor visual alignment while retaining their separate stylesheet and offline compatibility.

## Portfolio packaging

The portfolio phase adds a fixed fictional demo, professional public documentation, screenshot and privacy guidance, repository hygiene, and an allowlisted release builder. The release deliberately excludes private source materials, local environments, caches, generated downloads, and Git metadata.
