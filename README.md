# IOC Watchlist

Barebones IOC watchlist manager. FastAPI + SQLite backend, plain HTML/JS
frontend, no auth or styling.

## Run

```sh
uv run uvicorn ioc_watchlist.main:app --reload
```

or start via the installed script:

```sh
uv run ioc-watchlist
```

Then open <http://127.0.0.1:8000>.

- `/` — form to add an IOC (tags added one by one as chips)
- `/iocs` — list of all IOCs, filterable by type and tags, with delete buttons

The SQLite database is created on startup at `ioc_watchlist.db` (override with
the `IOC_WATCHLIST_DB` env var).

## API

All routes are under `/api`.

| Method | Path | Description |
| ------ | ---- | ----------- |
| POST   | `/api/iocs` | Create an IOC. Body: `{"value": "...", "tags": ["a", "b"]}` |
| GET    | `/api/iocs?type=&tags=` | List IOCs. Optional `type` filter, optional `tags` (comma-separated; an IOC must have **all** listed tags) |
| DELETE | `/api/iocs/{id}` | Delete an IOC. Returns 204 |

- The type (`ipv4`, `domain`, `url`, `md5`, `sha1`, `sha256`) is detected
  automatically from the value. Invalid values are rejected with a 400 and a
  clear message; unknown `type` filter values are also rejected.
- Defanged values are accepted and normalized, e.g. `1.2.3[.]4`,
  `evil[.]com`, `hxxp://bad[.]site/x` are stored fanged.
- Duplicate values are rejected with 409.
- IOCs and tags are many-to-many (`iocs`, `tags`, `ioc_tags` tables).
- Interactive docs: <http://127.0.0.1:8000/docs>
