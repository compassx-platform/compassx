import sqlparse


def validate_sql(sql: str, dialect: str = "duckdb") -> dict:
    del dialect
    statements = [stmt for stmt in sqlparse.parse(sql or "") if stmt.tokens]
    if not statements:
        return {"valid": False, "error": "Empty SQL"}
    return {"valid": True, "statement_count": len(statements)}


def extract_table_references(sql: str) -> list[str]:
    import sqlglot
    from sqlglot.errors import ParseError

    try:
        expression = sqlglot.parse_one(sql, read="duckdb")
    except ParseError as e:
        raise ValueError(f"SQL parsing failed: {str(e)}")

    tables = set()
    for table in expression.find_all(sqlglot.exp.Table):
        parts = []
        if table.catalog:
            parts.append(table.catalog)
        if table.db:
            parts.append(table.db)
        if table.name:
            parts.append(table.name)
        if parts:
            tables.add(".".join(parts))
    return list(tables)
