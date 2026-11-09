# Development log — prompts, build time, tokens

AI-assisted build history for the IOC watchlist manager (GLM via OpenCode).
All prompts below were issued on **2026-11-10** in a single session.

---

## Prompts (chronological)

### 1. Initial build request

> You need to build an IOC watchlist manager. We just need a barebones
> implementation and features like auth and css styling are not required as
> of now. The tech stack has to be html + js for frontend and fastapi
> backend with sqlite.
>
> - The home page should contain a form to make an IOC entry … a navbar
>   link to a page showing the list of all entered IOCs with the detected
>   type and tags. This page should be able to filter the list by type and
>   tags and a delete button for each IOC.
> - In backend we need to create FastAPI routes to create, list (with
>   optional tag and type filters) and delete IOCs.
> - The IOC types ipv4, domain, url, md5, sha1, sha256 is detected
>   automatically from value.
> - Reject values that are not valid for any supported type with clear
>   error.
> - Database: use sqlite. An IOC may have many tags and a tag can belong to
>   many iocs.
> - The current app is scaffolded with uv and fastapi and some dependencies
>   installed. Let me know if you need to decide before implementing any
>   business logic.

_Decision round answered_: accept & normalize defanged values · separate
add-tag chips widget · reject duplicates with a clear error · serve the
frontend from FastAPI.

### 2. Permission policy

> You, as the agent should not have edit permissions to create / edit
> files. Update your settings and ask permissions every time doing so.

### 3. Test suite

> Write extensive test cases for the business use case to test the backend
> business logic and routes. Ask questions if you want to confirm anything.

_Decision round answered_: create all test files under `tests/` (+ pytest
config in `pyproject.toml`) · in-process `TestClient`, no live-server tests.

### 4. Commit message

> Suggest a commit message

### 5. Raw + canonical storage, re-defanged listings

> The user inputs a fanged or defanged input. We need to store both the raw
> inputs and canonical value/hash for identifying uniqueness in DB. While
> listing the IOCs they should be served re-defanged values from the
> canonical values or hashes. Write relevant tests as well.

_Decision round answered_: POST echoes the original body (`value` + tags);
GET serves re-defanged values only (no raw/canonical exposed) · hashes
re-chunked with hyphens when displayed · raw column with first-entry-wins ·
auto-migrate the existing database.

### 6. Defanged-hash test gaps

> The test cases in `tests/test_detection.py` don't seem to have defanging
> tests. Identified gaps: 1) Zero defanged hash test cases (space-separated,
> bracketed, hyphenated chunking). 2) Intermediate boundary lengths (31/39/63
> characters) that might slip past loose regexes. Just add the test cases
> accordingly and don't make any changes in routes for now.

_Decision round answered_: implement chunk recovery in `detection.py` + the
tests; routes stay untouched.

### 7. Suggestions on the IOCs page

> Perfect, implement this in the tags field on iocs page as well

### 8. Autocomplete bug report

> The autocomplete does not work on /iocs page

![Placeholder: screenshot of the All IOCs page with "md" typed in the tags
filter and no suggestion popup](images/iocs-autocomplete-broken.png)

### 9. Filter semantics question

> `static/iocs.html` — What does "all must match" mean?

### 10. Match-mode toggle

> C, that should be better

_(meaning option C: an all/any match-mode toggle, keeping AND as the
default)_

### 11. Documentation & deployment

> The project is now deployed on render. Update the README in accordance
> with recent changes. Also include these details covering: what the
> project does, tech stack, architecture and design decisions, how to run
> it locally, how to run tests (if any), API endpoints, known limitations,
> what you would improve with more time, and any security or domain
> assumptions you made. Deployment instructions: step-by-step instructions
> to deploy the app, including required environment variables and how to
> seed or migrate the database. Also add instructions to setup locally. The
> command to run the app is `uv run uvicorn ioc_watchlist.main:app --host
> 0.0.0.0 --port $PORT`. In a separate file, list all the prompts from me
> and have placeholders for images (will add the actual screenshots later)
> that were prompted with you during the development so far. Add a section
> for Build time … A section for Tokens consumed …

---

## Build time

| | Timestamp | Duration |
|---|---|---|
| Start (first prompt received) | _fill in_ | – |
| End (app working & deployed) | _fill in_ | – |
| **Total (first prompt → working app)** | – | _fill in_ |

## Tokens consumed

_(from the provider usage dashboard — add the actual screenshot)_

| Metric | Value |
|---|---|
| Total input tokens | _fill in_ |
| Total output tokens | _fill in_ |
| Total tokens | _fill in_ |

![Placeholder: token usage dashboard screenshot](images/token-usage.png)
