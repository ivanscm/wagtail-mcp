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
