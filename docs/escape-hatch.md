# Escape hatch: `api_call` and `api_schema`

The 58 curated tools wrap the 60 hand-picked operations an agent most often
needs. Everything else in the v3 OpenAPI schema — and anything a future API
release adds — remains reachable through two generic tools:

- **`api_call(operation_id, path_params?, query?, body?)`** — call *any* v3
  operation by its `operation_id`.
- **`api_schema(component?)`** — read the project's full OpenAPI 3.1 document
  (paths + components) or one named schema component, to learn exact payloads
  and paths for `api_call`.

Both are read-only introspection over the same OpenAPI document the dispatch
layer uses to resolve `operation_id → method+path`, so they can never drift
from what the API actually serves.

## Discovering operations

Ask the model to enumerate the operation surface before driving unknown
operations:

```
api_schema
```

returns `{paths: [...], components: [...]}`. Operation ids share a
`<resource>_...` prefix (e.g. `pages_*`, `images_*`, `sites_*`, `whoami`), so
you can survey what a resource offers by its prefix. Request one schema
component by name to see its exact shape:

```
api_schema(component="PageMoveSchema")
```

## Unknown `operation_id`

Passing an `operation_id` the API doesn't know returns an `isError` result
listing the valid prefix groups, e.g.:

> Unknown operation_id "pages_bogus". Known prefixes: documents, images,
> locales, pages, redirects, schema, sites, snippets.

## Worked example: revert a page revision

Reverting a page to an earlier revision has a dedicated tool
(`pages_actions_revert`), but the same flow works through `api_call` — and is
what you'd do for a revision surface with no curated tool.

1. List the page's revisions to find the one to restore to:

   ```
   pages_revisions_list(page_id=12)
   ```

   → `{count, items: [{id, created_at, object_str, ...}]}`; note the target
   revision's `id`, say `7`.

2. Revert via `api_call`:

   ```
   api_call(
     operation_id="pages_actions_revert",
     path_params={"page_id": 12},
     body={"revision_id": 7},
   )
   ```

   The operation rewinds the page content to that revision and creates a new
   revision; read `pages_detail(page_id=12, version="draft")` to confirm the
   reverted content.

## Worked example: embed an image in a page body

The curated `pages_create`/`pages_update` tools take `body_markdown`, which is
wrapped as a Markdown envelope and converted server-side. **Markdown image
embeds (`![alt](wagtail://image?id=N)`) are silently dropped by the v3 write
sanitizer** (see [api-feedback](api-feedback.md)) — so to make an image
actually appear in a page body you must send the body as raw **DB HTML** via
`api_call`.

1. Upload the image to get its id:

   ```
   images_create(title="Teaser", content_base64="<base64>", filename="teaser.png")
   ```

   → note `id=42`.

2. Create the page with a raw `db_html` body containing a Wagtail embed tag:

   ```
   api_call(
     operation_id="pages_create",
     body={
       "meta": {"type": "wagtail_mcp_test.ContentPage", "parent_id": 1},
       "title": "Embed example",
       "body": '<embed embedtype="image" id="42" format="right" alt="Teaser"/>',
     },
   )
   ```

   A plain string `body` is interpreted as DB HTML (the same as Wagtail's rich
   text storage), so the embed survives. To later *read* it back as Markdown,
   use `pages_detail(rich_text_format="markdown")`, which resolves the embed to
   its rendition URL.

When old-style management of arbitrary operations is the goal, use
`api_call` for CRUD on a resource that has a curated tool only for reads, or
for operations the hand-curated set deliberately skips. The result of a
`204`/empty operation is normalised to `{}`.