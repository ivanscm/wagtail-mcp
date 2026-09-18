# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Paginated tools (`pages_list`, `images_list`, `documents_list`, `snippets_list`,
  `redirects_list`, `sites_list`, `locales_list`, and the revisions lists) now state the
  site's maximum `limit` in their descriptions, read from Wagtail's `WAGTAILAPI_LIMIT_MAX`
  setting (default 20), so agents no longer discover the cap from a 400 error.
- `pages_create` and `pages_update` now accept the base page write fields
  `slug`, `seo_title`, `search_description` and `show_in_menus`, plus a
  `fields` dict for any other writable field of the page type (typed
  arguments win on clashes). This removes the need for the `api_call` escape
  hatch for common page edits, including the raw `db_html` body workaround
  for image embeds.
- `pages_detail` now reports `meta.seo_title` and `meta.search_description`
  so agents can read back SEO edits.
- `images_create` accepts an optional `description`; `images_update` takes
  `title` and/or `description` with PATCH semantics.

### Fixed

- Detail tools no longer silently drop fields the v3 API returned. Responses
  from `pages_detail`, `pages_find`, page/snippet create, update and action
  tools, `*_revisions_detail`, `images_detail`, `documents_detail`,
  `sites_detail`, `locales_detail`, and the redirect detail tools now pass
  every field through, including empty strings and nulls — so an agent can
  tell "field is empty" (e.g. `meta.seo_title: ""`) from "field not exposed".
  List tools keep their compact summaries.

## [0.1.0] - 2026-08-27

First release ✨🤖 vibe-coded prototype built with pi and Kimi K3.

Please share your feedback on our plans: [CMS with AI, not AI CMS: Wagtail 8.0’s new API](https://wagtail.org/blog/cms-with-ai-not-ai-cms-wagtail-80s-new-api/).

<!-- TEMPLATE - keep below to copy for new releases -->
<!--


## [x.y.z] - YYYY-MM-DD

### Added

- ...

### Changed

- ...

### Removed

- ...

-->
