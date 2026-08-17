from fastapi import HTTPException


def enforce_policy(warehouse, records) -> None:
    policy = warehouse.resource_policy or {}
    max_concurrent = policy.get("max_concurrent_queries")
    if max_concurrent and records.count_active(str(warehouse.id)) >= int(max_concurrent):
        raise HTTPException(
            status_code=429,
            detail=f"Warehouse '{warehouse.name}' has reached its concurrent query limit of {max_concurrent}.",
        )

