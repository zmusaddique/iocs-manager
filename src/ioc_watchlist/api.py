from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response

from .db import get_conn
from .detection import IOC_TYPES, InvalidIOCError, defang_for_display, detect
from .schemas import IOCCreate, IOCCreated, IOCList, IOCRead, IOCTag

router = APIRouter(prefix="/api", tags=["iocs"])


def _clean_tags(tags: list[str]) -> list[str]:
    """Strip, lowercase and de-duplicate tag names while preserving order."""
    seen: set[str] = set()
    cleaned: list[str] = []
    for tag in tags:
        name = tag.strip().lower()
        if name and name not in seen and len(name) <= 64:
            seen.add(name)
            cleaned.append(name)
    return cleaned


def _get_or_create_tag_ids(conn, names: list[str]) -> list[int]:
    ids = []
    for name in names:
        row = conn.execute(
            "SELECT id FROM tags WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            cur = conn.execute("INSERT INTO tags (name) VALUES (?)", (name,))
            ids.append(cur.lastrowid)
        else:
            ids.append(row["id"])
    return ids


def _fetch_ioc_row(conn, ioc_id: int) -> dict | None:
    """Canonical row internals (canonical value kept under 'canonical')."""
    row = conn.execute(
        "SELECT id, value, raw_value, type, created_at FROM iocs WHERE id = ?",
        (ioc_id,),
    ).fetchone()
    if row is None:
        return None
    tag_rows = conn.execute(
        """
        SELECT t.id, t.name
        FROM ioc_tags it JOIN tags t ON t.id = it.tag_id
        WHERE it.ioc_id = ? ORDER BY t.name
        """,
        (ioc_id,),
    ).fetchall()
    return {
        "id": row["id"],
        "canonical": row["value"],
        "raw_value": row["raw_value"],
        "type": row["type"],
        "created_at": row["created_at"],
        "tags": [IOCTag(id=t["id"], name=t["name"]) for t in tag_rows],
    }


def _ioc_created(row: dict) -> IOCCreated:
    """POST response: echo the raw input exactly as submitted."""
    return IOCCreated(
        id=row["id"],
        value=row["raw_value"],
        type=row["type"],
        created_at=row["created_at"],
        tags=row["tags"],
    )


def _ioc_display(row: dict) -> IOCRead:
    """GET response: re-defanged from the canonical value."""
    return IOCRead(
        id=row["id"],
        value=defang_for_display(row["canonical"], row["type"]),
        type=row["type"],
        created_at=row["created_at"],
        tags=row["tags"],
    )


@router.post("/iocs", response_model=IOCCreated, status_code=201)
def create_ioc(payload: IOCCreate) -> IOCCreated:
    try:
        ioc_type, normalized = detect(payload.value)
    except InvalidIOCError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid IOC value: {exc.value!r} is {exc.reason}",
        ) from exc

    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(
            "SELECT id FROM iocs WHERE value = ?", (normalized,)
        ).fetchone()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"IOC {normalized!r} already exists "
                    f"(id {existing['id']})"
                ),
            )

        cur = conn.execute(
            "INSERT INTO iocs (value, raw_value, type) VALUES (?, ?, ?)",
            (normalized, payload.value, ioc_type),
        )
        ioc_id = cur.lastrowid

        tag_ids = _get_or_create_tag_ids(conn, _clean_tags(payload.tags))
        conn.executemany(
            "INSERT OR IGNORE INTO ioc_tags (ioc_id, tag_id) VALUES (?, ?)",
            [(ioc_id, tid) for tid in tag_ids],
        )

        created = _fetch_ioc_row(conn, ioc_id)

    assert created is not None
    return _ioc_created(created)


@router.get("/iocs", response_model=IOCList)
def list_iocs(
    type: str | None = Query(default=None),
    tags: str | None = Query(
        default=None,
        description="Comma-separated tag names; an IOC must have ALL of them",
    ),
) -> IOCList:
    if type is not None and type not in IOC_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown type {type!r}. Supported types: "
                + ", ".join(IOC_TYPES)
            ),
        )

    tag_names = [t.strip().lower() for t in (tags or "").split(",") if t.strip()]

    sql = """
        SELECT i.id, i.value, i.type, i.created_at
        FROM iocs i
    """
    params: list = []

    # SQL clause order: FROM -> JOIN -> WHERE -> GROUP BY -> HAVING.
    # Params must follow the same order: tag names (IN clause), then type.
    if tag_names:
        placeholders = ", ".join("?" for _ in tag_names)
        sql += f"""
            JOIN ioc_tags it ON it.ioc_id = i.id
            JOIN tags t ON t.id = it.tag_id AND t.name IN ({placeholders})
        """
        params.extend(tag_names)

    wheres = []
    if type:
        wheres.append("i.type = ?")
        params.append(type)

    if wheres:
        sql += "\nWHERE " + " AND ".join(wheres)

    if tag_names:
        sql += """
            GROUP BY i.id
            HAVING COUNT(DISTINCT t.id) = ?
        """
        params.append(len(tag_names))

    sql += " ORDER BY i.created_at DESC, i.id DESC"

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
        items = []
        for r in rows:
            row = _fetch_ioc_row(conn, r["id"])
            assert row is not None
            items.append(_ioc_display(row))
        return IOCList(items=items, total=len(items))


@router.delete("/iocs/{ioc_id}", status_code=204)
def delete_ioc(ioc_id: int) -> Response:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM iocs WHERE id = ?", (ioc_id,))
        if cur.rowcount == 0:
            raise HTTPException(
                status_code=404, detail=f"IOC id {ioc_id} not found"
            )
    return Response(status_code=204)
