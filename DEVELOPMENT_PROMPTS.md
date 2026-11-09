# Development log — prompts, build time, tokens

AI-assisted build history for the IOC watchlist manager (GLM
`opencode/glm-5.3-flash-free` via OpenCode). All prompts below were issued
on **2026-11-10** in a single session.

Screenshots under `images/` show the prompt/agent session as it unfolded
(filenames are sequential: `Pasted image (N).png`).

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

![Session screenshot: the initial build request and the agent's plan](./images/Pasted%20image.png)

### 2. Permission policy

> You, as the agent should not have edit permissions to create / edit
> files. Update your settings and ask permissions every time doing so.

### 3. Test suite

> Write extensive test cases for the business use case to test the backend
> business logic and routes. Ask questions if you want to confirm anything.

_Decision round answered_: create all test files under `tests/` (+ pytest
config in `pyproject.toml`) · in-process `TestClient`, no live-server tests.

![Session screenshot: the test-suite request](./images/Pasted%20image%20%282%29.png)

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

![Session screenshot: the raw/canonical + re-defanged listing request](./images/Pasted%20image%20%284%29.png)

### 6. Defanged-hash test gaps

> The test cases in `tests/test_detection.py` don't seem to have defanging
> tests. Identified gaps: 1) Zero defanged hash test cases (space-separated,
> bracketed, hyphenated chunking). 2) Intermediate boundary lengths
> (31/39/63 characters) that might slip past loose regexes. Just add the
> test cases accordingly and don't make any changes in routes for now.

_Decision round answered_: implement chunk recovery in `detection.py` + the
tests; routes stay untouched.

![Session screenshot: the defanged-hash test-gap report](./images/Pasted%20image%20%283%29.png)

### 7. Tag autocomplete on the home page

> While typing the tags, if any same tags exist it should pop up for
> selection. This will help us prevent having duplicated tag values and
> help in analysis. Do this only for the home page now.

![Session screenshot: the home-page tag autocomplete request](./images/Pasted%20image%20%285%29.png)

### 8. Suggestions on the IOCs page

> Perfect, implement this in the tags field on iocs page as well.

![Session screenshot: extending suggestions to the /iocs filter field](./images/Pasted%20image%20%286%29.png)

### 9. Autocomplete bug report

> The autocomplete does not work on /iocs page

![Screenshot: the All IOCs page with "md" typed in the tags filter and no
suggestion popup](./images/Pasted%20image%20%287%29.png)

### 10. Filter semantics question

> `static/iocs.html` — What does "all must match" mean?

![Session screenshot: the filter-semantics question](./images/Pasted%20image%20%288%29.png)

### 11. Match-mode toggle

> C, that should be better

_(meaning option C: an all/any match-mode toggle, keeping AND as the
default)_

![Session screenshot: the match-mode toggle request](./images/Pasted%20image%20%289%29.png)

### 12. Documentation & deployment

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

Wall-clock (analyst) vs machine (session) time, per the usage dashboard:

| Metric                       | Value              |
| ---------------------------- | ------------------ |
| Start (first prompt)         | 7:30 pm, 2026-11-10|
| End (app working & deployed) | 10:00 pm           |
| **Total wall-clock**         | **2.5 hrs**        |
| Session run time (machine)   | 1h 07m 15s         |

## Tokens consumed

From the session usage dashboard (OpenCode, model
`opencode/glm-5.3-flash-free`); totals include cached input reads, which is
why `total ≠ input + output`:

| Metric              | Value        |
| ------------------- | ------------ |
| Total input tokens  | 978,799      |
| Total output tokens | 63,066       |
| Reasoning tokens    | 61,210       |
| Cache read          | 9,011,904 (90.2% cache rate) |
| **Total tokens**    | **10,114,979** |
| **Estimated cost**  | **$0.48**    |
| Steps / tool calls  | 129 / 127    |

![Screenshot: OpenCode token-usage summary (context, input/output, cache,
cost)](./images/Pasted%20image%20%2810%29.png)

![Screenshot: OpenCode usage dialog (context breakdown and per-model
totals)](./images/Pasted%20image%20%2811%29.png)
