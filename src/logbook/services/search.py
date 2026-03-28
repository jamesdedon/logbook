from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def search(
    db: AsyncSession,
    query: str,
    entity_types: list[str] | None = None,
    limit: int = 20,
) -> list[dict]:
    """Full-text search across all entities using FTS5.

    Supports:
    - Multiple keywords: "auth refactor" matches entries containing both words
    - Prefix matching: "auth*" matches "auth", "authentication", "authorize"
    - Phrase matching: '"fix bug"' matches the exact phrase
    - Porter stemming: "running" matches "run", "runs", etc.
    """
    # FTS5 query — append * to each token for prefix matching by default
    tokens = query.strip().split()
    if not tokens:
        return []

    # If the user already used FTS5 operators, pass through as-is
    fts_operators = {'"', "*", "OR", "AND", "NOT", "NEAR"}
    if any(op in query for op in fts_operators):
        fts_query = query
    else:
        # Auto prefix-match each token
        fts_query = " ".join(f"{t}*" for t in tokens)

    type_filter = ""
    params: dict = {"query": fts_query, "limit": limit}
    if entity_types:
        placeholders = ", ".join(f":type_{i}" for i in range(len(entity_types)))
        type_filter = f"AND entity_type IN ({placeholders})"
        for i, t in enumerate(entity_types):
            params[f"type_{i}"] = t

    sql = text(f"""
        SELECT
            entity_type,
            entity_id,
            snippet(search_index, 2, '>>>', '<<<', '...', 32) as title_snippet,
            snippet(search_index, 3, '>>>', '<<<', '...', 64) as body_snippet,
            rank
        FROM search_index
        WHERE search_index MATCH :query
        {type_filter}
        ORDER BY rank
        LIMIT :limit
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    return [
        {
            "entity_type": row[0],
            "entity_id": row[1],
            "title_snippet": row[2],
            "body_snippet": row[3],
            "rank": row[4],
        }
        for row in rows
    ]
