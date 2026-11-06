"""Resolve the param values one job fans out over."""
from __future__ import annotations

from typing import List, Optional

import requests
from jsonpath_ng.ext import parse as jsonpath_parse
from sqlalchemy.orm import Session

from app.ingestion.composition import execution_logger
from app.ingestion.infrastructure.http_fetch import _build_auth_headers, _build_auth_params, _http_get_with_retry
from app.ingestion.infrastructure.rate_limit import _get_bucket
from app.ingestion.models import IngestionConnection, IngestionJobConfig
from app.ingestion.watermarks import NONE_SENTINEL

logger = execution_logger()


class ResolveParamValues:
    def execute(
        self,
        db: Session,
        job_config: IngestionJobConfig,
        connection: IngestionConnection,
        secret: Optional[str],
    ) -> List[str]:
        """
        Resolve the list of param values to fan out over.
        Handles: static | catalog_query | parent_api
        """
        ptype = job_config.param_source_type
        pcfg = job_config.param_source_config or {}

        if ptype == "static":
            vals = pcfg.get("values", [])
            if not vals:
                return [NONE_SENTINEL]
            return [str(v) for v in vals]

        if ptype == "catalog_query":
            # Call the catalog service to resolve asset values
            try:
                from app.catalog.services import query_catalog_values  # type: ignore
                results = query_catalog_values(
                    db,
                    object_type=pcfg.get("catalog_object_type", "asset"),
                    filters=pcfg.get("filter", {}),
                    value_field=pcfg.get("value_field", "external_id"),
                )
                return results or [NONE_SENTINEL]
            except ImportError:
                logger.warning("catalog_query param source: catalog service not available, returning __none__")
                return [NONE_SENTINEL]

        if ptype == "parent_api":
            # Call the parent endpoint to get a list of param values
            parent_path = pcfg.get("path_template", "")
            list_path = pcfg.get("response_list_path", "$[*]")
            value_field = pcfg.get("value_field", "id")

            url = connection.base_url.rstrip("/") + "/" + parent_path.lstrip("/")
            auth_headers = _build_auth_headers(connection, secret)
            auth_headers.update(dict(connection.default_headers or {}))
            auth_params = _build_auth_params(connection, secret)

            bucket = _get_bucket(str(connection.id), float(connection.rate_limit_rps))
            sess = requests.Session()
            try:
                _, data = _http_get_with_retry(
                    sess, url, auth_headers, auth_params, None, "GET", bucket
                )
                # Extract the list
                list_expr = jsonpath_parse(list_path)
                items = [m.value for m in list_expr.find(data)]
                values = []
                for item in items:
                    if isinstance(item, dict):
                        values.append(str(item.get(value_field, "")))
                    else:
                        values.append(str(item))
                return values or [NONE_SENTINEL]
            except Exception as exc:
                logger.error("parent_api param resolution failed: %s", exc)
                return [NONE_SENTINEL]

        logger.warning("Unknown param_source_type=%s, defaulting to __none__", ptype)
        return [NONE_SENTINEL]


def resolve_param_values(
    db: Session,
    job_config: IngestionJobConfig,
    connection: IngestionConnection,
    secret: Optional[str],
) -> List[str]:
    return ResolveParamValues().execute(db, job_config, connection, secret)
