# IOC Watchlist

A barebones, single-analyst IOC (Indicator of Compromise) watchlist manager.
Analysts paste potentially fanged/defanged values (`1.2.3.4`,
`1.2.3[.]4`, `hxxp://bad[.]site/x`, chunked hashes), the app detects the IOC
type automatically, stores the entry with tags, and serves a filterable list
for triage. Built deliberately without auth or styling — correctness of the
business logic first.

> Screenshots and development-notes live in
> [`DEVELOPMENT_PROMPTS.md`](DEVELOPMENT_PROMPTS.md).

## What it does

- **Add IOCs** on the home page: paste a value (fanged, defanged or clean),
  attach zero or more tags via a chip widget with autocomplete of existing
  tags.
- **Automatic type detection** across `ipv4`, `domain`, `url`, `md5`,
  `sha1`, `sha256` — anything else is rejected with a clear error.
- **Defange-aware everywhere**: defanged inputs are stored in canonical
  (fanged) form; the list view re-defangs canonical values for safe display
  (`8.8.8[.]8`, `hxxp://evil[.]com/`, hashes re-chunked with hyphens).
- **List, filter, delete** on the IOCs page: filter by type, by tags
  (match **all** or **any** — toggleable), delete individual IOCs.
- Many-to-many tags: an IOC may have many tags, a tag may belong to many
  IOCs; tags are normalized (trimmed, lowercased) and shared.

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | Vanilla HTML + JS (no framework, no build step, no CSS by design) |
| Backend | Python 3.12, FastAPI, Pydantic v2 |
| Database | SQLite via the standard library (`sqlite3`), no ORM |
| Normalization | [`ioc-fanger`](https://pypi.org/project/ioc-fanger/) (fang), `url-normalize` (URL canonicalization) |
| Tests | pytest + FastAPI `TestClient` (265 tests) |
| Packaging | [uv](https://docs.astral.sh/uv/) project layout (`src/` layout, `uv.lock`) |
| Server | uvicorn (single ASGI worker; SQLite-appropriate) |

## Architecture & design decisions

```
src/ioc_watchlist/
├── detection.py   # pure functions: type detection + fang/defang transforms
├── db.py          # sqlite connection, schema, idempotent migration
├── schemas.py     # request/response models (create-echo vs display-read)
├── api.py         # /api routes: create, list (filters), delete, tag list
└── main.py        # app assembly, lifespan (schema init), static serving

static/            # index.html (create), iocs.html (list) + small JS files
```

Key decisions:

- **Canonical value is the identity.** Every stored IOC has a `raw_value`
  (first submission's exact spelling) and a canonical `value` (fanged) that
  carries the UNIQUE constraint. `1.2.3.4`, `1.2.3[.]4` and
  `8.8.8[.]8` therefore all collapse into one entry; duplicates return 409.
- **Two response contracts.** `POST /api/iocs` echoes the raw input verbatim
  (what the analyst typed); `GET` responses serve a re-defanged display value
  derived from the canonical one. Raw and canonical values are never exposed
  in listings.
- **Defang pipeline.** `ioc-fanger` handles classic defang forms (`[.]`,
  `(.)`, `[dot]`, `hxxp`, `[at]`…). Hash chunking (spaces/hyphens/brackets)
  is recovered in our code and only engages when the result is pure hex of
  exactly md5/sha1/sha256 length — so hyphens in domains/URLs are untouched.
  URL canonicalization by `url-normalize` (lowercase scheme/host, strip
  default ports, add trailing slash) makes e.g. `HTTP://Example.com:80` and
  `http://example.com/` the same IOC.
- **Display defanging is hand-rolled**, not `ioc-fanger.defang`: scheme →
  `hxxp`/`hxxps`, every dot in the URL becomes `[.]`, and hashes are
  re-chunked into 8-char hyphenated blocks. This is deterministic and
  fangs back losslessly.
- **No ORM.** Plain parameterized SQL with a tiny connection helper; the
  schema is created and legacy-migrated idempotently in the app lifespan,
  so deploys need no migration step (see
  [Deployment](#deployment-render)).
- **Filter semantics are explicit.** The tags filter is AND by default with
  an `all_tags=false` OR mode; unknown type filters are rejected (400), not
  silently ignored.
- **Browsers always revalidate** static pages/JS (`Cache-Control:
  no-cache`); a deploy can never be masked by stale cached assets.

## Run locally

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/)
(Python 3.12 is pinned via `.python-version`).

```sh
git clone <your-repo-url>
cd ioc-watchlist
uv sync                    # install dependencies into .venv

# run the app
uv run uvicorn ioc_watchlist.main:app --reload
# alternative: uv run ioc-watchlist  (binds 127.0.0.1:8000)

open http://127.0.0.1:8000
```

- `http://127.0.0.1:8000/` — add IOCs (form with tag chips + suggestions)
- `http://127.0.0.1:8000/iocs` — list/filter/delete
- `http://127.0.0.1:8000/docs` — interactive OpenAPI docs

The SQLite database is created (and any legacy schema migrated) on first
startup at `ioc_watchlist.db`, overridable with `IOC_WATCHLIST_DB`.

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `IOC_WATCHLIST_DB` | `ioc_watchlist.db` | SQLite file path (set it to a mounted/absolute path in deployment) |
| `PORT` | – | Injected by the platform (Render); consumed by the start command |
| `PYTHON_VERSION` | `.python-version` (3.12) | Render Python runtime version |

## Run tests

```sh
uv run pytest        # 265 tests
uv run pytest -q     # quiet output
uv run pytest tests/test_detection.py -v   # a single module
```

The suite covers: type detection and defang normalization edge cases, DB
constraints/cascades/migration, every route contract (raw-echo create,
re-defanged listings, AND/ANY tag filters, duplicates, deletion), the tag
suggestion endpoint, static page/JS contract and cache revalidation
headers, and end-to-end workflows including persistence across restarts.
All tests run in-process via `TestClient` against a per-test SQLite file —
no network, no live server needed.

## API endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/iocs` | Create IOC: `{"value": "...", "tags": ["a","b"]}` → 201. Echoes the raw `value`; 400 invalid value, 409 duplicate, 422 bad payload |
| `GET` | `/api/iocs` | List: optional `type=`, `tags=` (comma-separated), `all_tags=true|false` (default true). Serves re-defanged values |
| `DELETE` | `/api/iocs/{id}` | Delete → 204, or 404 |
| `GET` | `/api/tags` | Existing tag names (alphabetical), optional `?q=` substring filter — powers the suggestion popups |
| `GET` | `/`, `/iocs` | Static pages served by FastAPI |
| `GET` | `/docs` | OpenAPI UI |

```sh
# create (defanged input is fine)
curl -X POST $BASE/api/iocs -H 'Content-Type: application/json' \
  -d '{"value": "hxxp://bad[.]site/gate[.]php", "tags": ["C2", "Malware "]}'
# 201 -> {"id": 1, "value": "hxxp://bad[.]site/gate[.]php", "type": "url",
#         "tags": [{"id":1,"name":"c2"},{"id":2,"name":"malware"}], ...}

# list: any of the tags c2/phising (re-defanged values in `value`)
curl "$BASE/api/iocs?tags=c2,phising&all_tags=false"

# delete
curl -X DELETE $BASE/api/iocs/1 -w '%{http_code}'   # 204 (404 if missing)
```

## Deployment (Render)

Deployed as a Render **Web Service** with the native Python runtime.

1. **Push the repo** to GitHub/GitLab (commit `pyproject.toml`,
   `uv.lock`, `.python-version`, `src/`, `static/`, `tests/`, `README.md`).
2. **Render → New → Web Service**, connect the repository.
3. **Runtime**: Python 3.12 (`PYTHON_VERSION=3.12`).
4. **Build command**:
   ```sh
   pip install uv && uv sync --no-dev --frozen
   ```
5. **Start command**:
   ```sh
   uv run uvicorn ioc_watchlist.main:app --host 0.0.0.0 --port $PORT
   ```
   (`$PORT` is injected by Render.)
6. **Health check path**: `/iocs` (or `/`).
   Optional: set the root URL… not needed; pages are served at `/`.
7. **Database persistence (important)**: SQLite needs a writable, persistent
   path. On Render, attach a **Disk** (paid instance types) mounted at e.g.
   `/var/data` and set:
   ```sh
   IOC_WATCHLIST_DB=/var/data/ioc_watchlist.db
   ```
   Without a persistent disk (free tier), the DB only lives in the
   container filesystem and is **wiped on every deploy/restart**.
8. **Environment variables**: none are required beyond the disk path above
   (the app has no secrets/auth); add any proxy settings Render needs.

**Migration & seeding**: zero-step by design. On startup the app creates
any missing tables and idempotently migrates legacy schemas (e.g. it
backfills `raw_value` from canonical values). To seed a fresh database:

```sh
curl -X POST $BASE/api/iocs -H 'Content-Type: application/json' \
  -d '{"value": "8.8.8.8", "tags": ["dns", "malware"]}'
```
or create a few entries via `/docs`.

<details>
<summary>Alternative: Docker (optional, not used by the Render deploy)</summary>

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
COPY . .
RUN uv sync --no-dev --frozen
ENV IOC_WATCHLIST_DB=/data/ioc_watchlist.db
VOLUME /data
EXPOSE 8000
CMD ["sh", "-c", "uv run uvicorn ioc_watchlist.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```
```sh
docker run -p 8000:8000 -v ioc_data:/data ioc-watchlist
```
</details>

## Known limitations

- **SQLite / single worker**: one uvicorn worker; SQLite's file-lock model
  suits this, but the app must not be horizontally scaled to multi-instance,
  and concurrent writers serialize briefly on `BEGIN IMMEDIATE`.
- **No pagination**: the list endpoint returns everything filtered; fine
  for a watchlist, not for tens of thousands of rows.
- **No update endpoint**: IOCs are immutable once created (delete +
  re-create instead) — tags of an existing IOC cannot be edited.
- **Near-duplicate tags still possible**: `phising` vs `phishing` can
  coexist; the suggestion popup only *nudges* toward existing tags, it does
  not hard-block typo variants, and there is no tag-rename/merge endpoint.
- **Frontend logic untested in automation**: page JS is validated by static
  contract tests (markup/scripts/headers), not by browser-level tests.
- **No bulk import/export** (STIX/MISP/CSV) and no IOC history/audit trail.
- `ioc-fanger` quirk: `http:///path` is rewritten by the library to
  `http://path` (single-label host), which is then a valid URL — documented
  behavior, surprising on first glance.

## With more time

1. **Pagination + server-side sorting** and value search on the list API.
2. **IOC update/edit** route and a tag **rename/merge** endpoint (fixes the
   `phising`-style data debt).
3. **Auth** (single API key or session login) and per-analyst audit rows.
4. **Docker + docker-compose** as a first-class deploy path, and Postgres
   behind an `asyncpg`/SQLAlchemy layer if usage outgrows SQLite.
5. **Enrichment hooks**: optional VirusTotal/AbuseIPDB lookups surfaced as
   read-only metadata columns.
6. **Browser-level tests** (Playwright) for the suggestion popup, filters,
   and delete flows, plus a JS linter; Python lint/mypy in CI.
7. **Import/export**: CSV + STIX bundles; manual UI for merging duplicate
   tags discovered by analysis.
8. Page styling and a small component framework once "barebones" stops
   being the requirement.

## Security & domain assumptions

- **No authentication/authorization by design** — assumes deployment as an
  internal, single-team, LAN/VPN tool. Render deployment is exposed
  publicly unless protected at the platform level; add auth or Render's
  built-in protection before sharing outside the team.
- **SQL injection**: all statements are fully parameterized; the only
  user-supplied SQL fragment (tag IN-list) is built from `?` placeholders;
  the `type` filter is validated against a whitelist.
- **XSS**: all user data is inserted through DOM `textContent` (frontend)
  and there is no server-side HTML templating; JSON is enforced by
  Pydantic with length caps (value ≤ 4096 raw, tag name ≤ 64).
- **Rate limiting / abuse** is out of scope; value length caps and integer
  path-validation are the only input guards.
- **CORS**: not configured — the API is same-origin only (served by the
  same FastAPI app).
- **Domain semantics**:
  - defanged input is *expected and accepted*; stored canonical, displayed
    re-defanged.
  - domain requires ≥2 labels and an alphabetic TLD; single-label hosts
    (`localhost`) are not domains — but may appear as URL hosts.
  - punycode is not auto-encoded; non-ASCII hostnames are rejected.
  - IPv6 is unsupported everywhere (values and URL hosts are rejected).
  - hash detection requires exact md5/sha1/sha256 lengths of hex — leading
    zeros and mixed case are fine, other lengths are not hashes.
  - "IOC" here means network observables only; file paths, CVEs, mutexes
    etc. are intentionally rejected as invalid.

## Development log

Prompt-by-prompt history, build-time and token accounting:
[`DEVELOPMENT_PROMPTS.md`](DEVELOPMENT_PROMPTS.md).
