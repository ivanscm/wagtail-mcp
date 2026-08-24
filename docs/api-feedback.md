# API feedback for the Wagtail v3 API

These are findings from building wagtail-mcp against the Wagtail v3 API,
written to be shareable with the Wagtail maintainers. Each is: what we
observed, why it hurts an MCP/agent perspective, and a suggested change. Our
workarounds in wagtail-mcp are noted where relevant. The raw working notes live
in `local/superpowers/api-feedback-notes.md`; this is the cleaned-up copy.

## Rich text write input is an envelope, not the `rich_text_format` query

- **Observed.** For page create/update, sending a plain `body` string is
  interpreted as DB HTML (via `APIRichText.parse_input`), *not* Markdown. To
  send Markdown you must pass the envelope `{"format": "db_markdown",
  "content": "..."}`. The `rich_text_format` query parameter affects **read**
  serialization only; the write schema never reads it.
- **Why it hurts.** The read side's `rich_text_format=markdown` strongly
  suggests the write side accepts markdown the same way, so an agent that
  echoes a markdown body straight back gets HTML, or sends a bare markdown
  string that is stored as HTML. It's easy to get wrong from the docs.
- **Suggested change.** Either accept plain markdown on write too, or make the
  write envelope the documented, discoverable path (schema-level union or
  clearer field description).
- **wagtail-mcp:** its curated write tools wrap markdown in the
  `db_markdown` envelope explicitly.

## Markdown image embeds are silently dropped on write

- **Observed.** A markdown image embed `![alt](wagtail://image?id=N)` is
  converted to `<embed data-embedtype="image" data-id="N" data-alt="alt"/>`,
  which the image-feature whitelister then censors with reason
  `missing_attribute` (the markdown importer's `data-*` attribute spelling
  doesn't match the `embed[embedtype="image"]` rule). The page still publishes
  live, but the image silently disappears — no error.
- **Why it hurts.** Silent content loss is the worst failure mode for an agent:
  it believes the image shipped. Because it's a success-path 422-free write,
  nothing alerts the caller.
- **Suggested change.** The markdown image exporter should emit
  `embedtype`/`id`/`alt`/`format` attributes (not `data-*`), **or** the
  whitelister should accept the markdown-produced spelling, so round-tripping
  markdown ↔ DB HTML preserves image embeds.
- **wagtail-mcp:** documents `db_html` bodies via the escape hatch as the
  working path (see `docs/escape-hatch.md`).

## Write schemas only expose `api_fields` marked `writable=True`

- **Observed.** A field declared `APIField("body")` (without `writable=True`)
  is read-only for writes: the create/patch schemas silently omit it, and it
  simply never stores. Silently, not with an error.
- **Why it hurts.** An agent creating a page gets a 200 and a stored page that
  is missing content it explicitly sent.
- **Suggested change.** At minimum, error or warn when a write excludes a field
  the caller supplied; or make writability the explicit, discoverable default
  for API fields intended to be edited.

## `pages_actions_move`'s `destination_id` is a target, not a parent

- **Observed.** `MovePageAction.execute()` sets `parent_after = target` only
  when `position` is a child value (`first-child`, `last-child`,
  `sorted-child`); otherwise `parent_after = target.get_parent()` and the
  moved page becomes a *sibling* of the target. So `{destination_id: X}`
  alone moves the page next to X, not under it.
- **Why it hurts.** The parameter name `destination_id` reads like "the page to
  become the new parent", which is the common case — an agent moving content
  under a section gets it placed beside the section instead.
- **Suggested change.** Document the target-vs-parent semantics, or expose a
  distinct `parent_id`-style parameter for the "move under X" case, or derive
  placement from a `position` enum with wide defaults.

## `pages_actions_unpublish` is not idempotent

- **Observed.** Unpublishing an already-unpublished page returns 403
  `{"detail": "You do not have permission to unpublish this page."}` on the
  second call.
- **Why it hurts.** Agents retry or run the same workflow twice; a clear
  "already unpublished" signal beats a misleading permission error.
- **Suggested change.** Make the endpoint idempotent, or return a distinct
  "already unpublished" outcome.

## Per-app router mounting silently drops route groups

- **Observed.** The v3 API's route groups are registered by the apps that own
  them (e.g. `wagtail.locales` adds `locales_*` in its `apps.ready()`). Omit
  an optional app from `INSTALLED_APPS` and its whole tool/resource group
  silently disappears from the OpenAPI schema — no error or hint.
- **Why it hurts.** An agent (or operator) probing the schema can't tell why a
  resource is absent; a downstream tool set is contingent on installed apps.
- **Suggested change.** Note this in the v3 quickstart, and/or expose which
  apps/route groups are and aren't registered in the API's discovery surface.

## `sites_update` is a full PUT, not a PATCH

- **Observed.** `SiteInputSchema` requires `hostname` and `root_page_id`, so a
  partial update (only `site_name`) 422s unless those required fields are also
  sent.
- **Why it hurts.** Agents expect PATCH semantics on update; a partial edit
  fails unless they fetch-then-merge.
- **Suggested change.** Either document update as PUT, or make required fields
  optional on update for genuine PATCH behavior.
- **wagtail-mcp:** its `sites_update` tool fetch-merges to emulate PATCH.

## No tags write field on image/document schemas

- **Observed.** `ImageCreateSchema`/`ImagePatchSchema`/`DocumentCreateSchema`
  expose no tags input; tags are read-only under `meta.tags`.
- **Why it hurts.** Taggable content can't be tagged from an agent, which is a
  common editorial need.
- **Suggested change.** Add a writable tags field to the image/document write
  schemas (or formally support taggable `api_fields` generically).

## Snippet specifics worth surfacing

- **Observed (write shape).** Snippet create/update bodies take fields
  directly — there is **no `meta.type`** (unlike pages); the type is the URL
  `/snippets/{type}/` path parameter. Snippet type strings are
  **case-sensitive** (`app_label.ModelName`); a wrong-case or unregistered
  label returns 422 `literal_error` at path `type`, not 404.
- **Observed (search).** Snippet `search` requires the model to declare
  `search_fields`; otherwise the list endpoint returns 422 "Not indexed for
  search", not empty results.
- **Observed (actions).** The action/revision endpoints only exist for models
  with the relevant mixins (`DraftStateMixin`, `RevisionMixin`,
  `TranslatableMixin`); calling them against a plain snippet returns 422.
- **Why it hurts.** These are discoverable only by trial; an agent that reaches
  for a snippet action on the wrong model gets an opaque 422.
- **Suggested change.** Clearer error signals (404 vs 422 distinction,
  capability hints) and documenting mixedin-only endpoints in the schema would
  reduce friction.

## Misc

- **`whoami` requires auth** (401 without a bearer token). Expected for a
  write-oriented API; worth noting that only read endpoints are anonymous.
- **`pages_delete` and `pages_actions_delete` are the same operation** — both
  are stacked decorators on the same delete view, differing only in path and
  `operation_id`. Tool descriptions note this is parity, not distinct
  behavior.
- **`meta.action` is `Literal["publish"] | None`** — there is no `"draft"`
  literal; omitting `action` means draft.
- **Redirect old paths are normalized** (trailing slash stripped) on
  create/update.
- **`redirects_list` has no `search`** — CRUD only, no text search (unlike
  images/documents/snippets lists).

## In-process client (django-ninja) findings

These are about dispatching the v3 API in-process via django-ninja's
`TestClient`; wagtail-mcp moved to Django's `test.Client` and these are
recorded for upstream reference.

- **Ninja's `TestClient` cannot serialize page responses.** Page schemas call
  `page.get_full_url(request)` with the serialization context request, which
  under Ninja's `TestClient` is a Mock (no host) — so page responses blow up
  with `TypeError: ... got 'Mock'` and the whole operation returns a bogus 422
  *after* the object was created. Injecting META doesn't help because the
  context request is a Mock. Upstream suggestion: Ninja's in-process client
  should build a fully functional `HttpRequest` (with a host) rather than a
  Mock user/context, or page schemas should not thread `request` into
  `get_full_url` when `WAGTAILAPI_BASE_URL` is set.
- **`pages_find` is a 302 redirect** to the page-detail URL; a real HTTP client
  must follow it (Django's `test.Client` does with `follow=True`). Also true of
  the hosted API.