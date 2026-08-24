# Tool reference

wagtail-mcp ships **60 tools**. Except `api_call` and `api_schema`, every tool
name is a Wagtail v3 API `operation_id` — the same names appear in the API's
OpenAPI schema, the escape hatch, the docs, and the tools themselves, so the
vocabulary is stable and shared.

Every tool carries MCP annotations so clients show sensible confirmations and
badges: **read-only** tools are marked with a read-only hint, **destructive**
ones (deletes, unpublish) with a destructive hint, and idempotent reads with
an idempotency hint. The convention below — `RO` = read-only,
`WRITE` = mutating, `DEST` = destructive — mirrors the annotation.

Common conventions across tools:

- **Read-first**: content-producing tools whose payloads depend on the
  project's models tell you to call `schema_detail(type)` (or
  `schema_list`) before creating/updating — do that first so you send valid
  fields.
- **Markdown by default**: content reads return rich text as Markdown unless
  you pass `rich_text_format="html"`.
- **`next_offset`** in list responses: paginate by passing it back as
  `offset`. `limit`/`offset` paginate every list tool.
- **Rich text writes** are Markdown envelopes converted server-side, **except**
  that Markdown image embeds are dropped by the v3 sanitizer — see the
  [escape hatch](escape-hatch.md) for the `db_html` workaround.
- **Errors**: tool failures are `isError` results with the v3 API's RFC 7807
  payload flattened (status, title, detail, per-field errors) plus a
  status-specific hint.

## Meta (5)

| Tool | Type | Purpose | Read first |
|---|---|---|---|
| `whoami` | RO | Confirm which Wagtail user the token maps to. | — |
| `schema_list` | RO | All content types (page + API-enabled snippet types) as `app_label.ModelName`. | — |
| `schema_detail` | RO | Full writable field schema for one type, incl. required fields. | `schema_list` |
| `api_schema` | RO | The project's full OpenAPI 3.1 doc, or one named component. | — |
| `api_call` | WRITE | Escape hatch: call any v3 operation by `operation_id`. | `api_schema` |

## Pages (17)

| Tool | Type | Purpose | Read first |
|---|---|---|---|
| `pages_list` | RO | List pages; filter by `child_of`/`descendant_of` (`'root'` or a page id) or `search`. | — |
| `pages_find` | RO | Find a page by URL path (e.g. `'blog/my-post/'`); `site` is its hostname for non-default sites. | — |
| `pages_detail` | RO | One page's detail; `version` live/draft; markdown by default. | — |
| `pages_create` | WRITE | Create a page (draft unless `publish=True`). | `schema_detail` |
| `pages_update` | WRITE | Patch an existing page (`publish=True` to publish the change). | `pages_detail` |
| `pages_delete` | DEST | Permanently delete a page (and descendants). | — |
| `pages_actions_delete` | DEST | Same delete via `/actions/delete/` (parity with the REST surface). | — |
| `pages_actions_publish` | WRITE | Publish the latest revision. | `pages_revisions_list` |
| `pages_actions_unpublish` | DEST | Take a live page offline; **not idempotent** (see below). | `pages_detail` |
| `pages_actions_copy` | WRITE | Copy a page (optionally its subtree) to a destination. | — |
| `pages_actions_move` | WRITE | Move a page relative to `destination_id` (see below). | — |
| `pages_actions_revert` | WRITE | Revert to an earlier revision (creates a new revision). | `pages_revisions_list` |
| `pages_actions_convert_alias` | WRITE | Turn an alias page into a regular independent page. | — |
| `pages_actions_create_alias` | WRITE | Create an alias mirroring a published page. | — |
| `pages_actions_copy_for_translation` | WRITE | Copy a page for translation into another locale. | `locales_list` |
| `pages_revisions_list` | RO | List a page's revisions (most recent first). | — |
| `pages_revisions_detail` | RO | One revision's full content snapshot. | `pages_revisions_list` |

Page-specific notes:

- `pages_actions_unpublish` is **not idempotent**: unpublishing an
  already-unpublished page errors with 403, so check
  `pages_detail(version="live")` first if unsure.
- `pages_actions_move`'s `destination_id` is a *target*, not a new parent. Pass
  a child position (`'last-child'`/`'first-child'`) to place the page **under**
  the destination; otherwise it becomes a **sibling** of it (its parent becomes
  the destination's own parent).
- `pages_actions_copy_for_translation` has `copy_parents` (also translate
  untranslated ancestors), `alias` (aliases instead of copies) and `recursive`.

## Images (5)

| Tool | Type | Purpose | Read first |
|---|---|---|---|
| `images_list` | RO | List images; optional `search` (matches title). | — |
| `images_detail` | RO | One image's detail (dimensions, description, focal point, URLs, tags). | — |
| `images_create` | WRITE | Upload an image (base64 + filename; content type inferred from extension). | — |
| `images_update` | WRITE | Update an image's title. | `images_detail` |
| `images_delete` | DEST | Permanently delete an image. | — |

Upload notes: `content_base64` must be actual file bytes in base64 (not a URL
or path). `content_type` is inferred from the extension (`.png`, `.jpg`,
`.jpeg`, `.gif`, `.webp`, `.svg`) when omitted. Image bytes are validated by
Pillow — a non-image upload 422s. **Tags are not writable** through the v3
write schema (see [api-feedback](api-feedback.md)); they're read-only under
`meta`.

## Documents (5)

| Tool | Type | Purpose | Read first |
|---|---|---|---|
| `documents_list` | RO | List documents; optional `search`. | — |
| `documents_detail` | RO | One document's detail (title, URLs, tags). | — |
| `documents_create` | WRITE | Upload a document (base64; any file type accepted). | — |
| `documents_update` | WRITE | Update a document's title. | `documents_detail` |
| `documents_delete` | DEST | Permanently delete a document. | — |

Same upload conventions as images; documents accept arbitrary bytes (no
content sniffing). Content types inferred from `.pdf`, `.txt`, `.md`,
`.markdown`, `.csv`, `.json`, `.doc`, `.docx`.

## Snippets (12) — generic, keyed by type

Snippet tools are generic over the snippet model: every one takes a `type`
string of the form `app_label.ModelName`. **Type strings are case-sensitive**
and must be registered (API-enabled, i.e. models with `api_fields`) — a wrong
label returns a 422, not a 404. Call `schema_list` to discover the available
types and `schema_detail(type)` before `snippets_create`/`snippets_update`.

| Tool | Type | Purpose | Read first |
|---|---|---|---|
| `snippets_list` | RO | List snippets of a type; optional `search`. | `schema_list` |
| `snippets_detail` | RO | One snippet's detail; `version` live/draft. | `schema_list` |
| `snippets_create` | WRITE | Create a snippet with `data` fields (`publish=True` to publish on write). | `schema_detail` |
| `snippets_update` | WRITE | Patch a snippet's `data` (PATCH semantics). | `schema_detail` |
| `snippets_delete` | DEST | Permanently delete a snippet. | — |
| `snippets_actions_delete` | DEST | Same delete via `/actions/delete/` (parity). | — |
| `snippets_revisions_list` | RO | List a snippet's revisions (most recent first). | — |
| `snippets_revisions_detail` | RO | One revision's full content snapshot. | `snippets_revisions_list` |
| `snippets_actions_publish` | WRITE | Publish a draftable snippet's latest revision. | — |
| `snippets_actions_unpublish` | DEST | Unpublish a live snippet. | — |
| `snippets_actions_revert` | WRITE | Revert a draftable snippet to an earlier revision. | `snippets_revisions_list` |
| `snippets_actions_copy_for_translation` | WRITE | Copy a translatable snippet for translation into a locale. | `locales_list` |

Mixins matter: the action/revision endpoints only exist for snippet models
with the relevant mixins — publish/unpublish need `DraftStateMixin`,
revisions/revert need `RevisionMixin`, copy-for-translation needs
`TranslatableMixin` (plus i18n enabled). Calling an action against an
incompatible type returns 422 from the API, which the tool passes through.

## Redirects (6)

| Tool | Type | Purpose | Read first |
|---|---|---|---|
| `redirects_list` | RO | List every redirect. | — |
| `redirects_find` | RO | Find the redirect for a given old path (404 when none). | — |
| `redirects_detail` | RO | One redirect's detail by id. | — |
| `redirects_create` | WRITE | Create a redirect (old path → page id or external URL). | — |
| `redirects_update` | WRITE | Update a redirect; target is preserved unless changed. | — |
| `redirects_delete` | DEST | Permanently delete a redirect. | — |

Notes: old paths are normalized (trailing slash stripped) on create/update.
`redirects_update` preserves the existing link/page target unless you pass a
new one; passing `redirect_page_id` clears an external link and vice versa.
`redirects_list` has no text search (CRUD only).

## Sites (5)

| Tool | Type | Purpose | Read first |
|---|---|---|---|
| `sites_list` | RO | List sites (hostname, port, name, root page). | — |
| `sites_detail` | RO | One site's detail by id. | — |
| `sites_create` | WRITE | Create a site on a `root_page_id`. | `pages_list` |
| `sites_update` | WRITE | Update a site (partial-update ergonomics via fetch-merge). | `sites_detail` |
| `sites_delete` | DEST | Permanently delete a site. | — |

`hostname` is the key (often with an optional `:port`).

## Locales (5)

| Tool | Type | Purpose | Read first |
|---|---|---|---|
| `locales_list` | RO | List locales (language code, display name, default flag). | — |
| `locales_detail` | RO | One locale's detail by id. | — |
| `locales_create` | WRITE | Create a locale for a language code (e.g. `'fr'`). | — |
| `locales_update` | WRITE | Update a locale's language code. | — |
| `locales_delete` | DEST | Permanently delete a locale. | — |

Locale create/update only accept codes within Wagtail's configured content
languages. `locales_delete` refuses to delete the last remaining or in-use
locale.
