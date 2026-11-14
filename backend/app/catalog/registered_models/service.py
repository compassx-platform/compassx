"""Create, version, and alias registered models in the data catalog.

Public names stay importable from this module. Each one forwards to one action.
"""
from __future__ import annotations

import logging

from app.catalog.registered_models.application.register_version import Registration

logger = logging.getLogger("app.catalog.registered_models")

_NAME_PATTERN_MESSAGE = "Model names start with a letter and contain letters, numbers, '_' or '-'."


def get_model(db, catalog_name, schema_name, name):
    from app.catalog.registered_models.application.get_model import get_model as action
    return action(db, catalog_name, schema_name, name)


def list_models(db, catalog_name=None, schema_name=None):
    from app.catalog.registered_models.application.list_models import list_models as action
    return action(db, catalog_name, schema_name)


def list_in_schema(db, catalog_name, schema_name):
    from app.catalog.registered_models.application.list_in_schema import list_in_schema as action
    return action(db, catalog_name, schema_name)


def create_model(db, catalog_name, schema_name, name, comment, user):
    from app.catalog.registered_models.application.create_model import create_model as action
    return action(db, catalog_name, schema_name, name, comment, user)


def update_model(db, catalog_name, schema_name, name, body, user):
    from app.catalog.registered_models.application.update_model import update_model as action
    return action(db, catalog_name, schema_name, name, body, user)


def delete_model(db, catalog_name, schema_name, name):
    from app.catalog.registered_models.application.delete_model import delete_model as action
    return action(db, catalog_name, schema_name, name)


def set_alias(db, catalog_name, schema_name, name, body, user):
    from app.catalog.registered_models.application.set_alias import set_alias as action
    return action(db, catalog_name, schema_name, name, body, user)


def delete_alias(db, catalog_name, schema_name, name, alias, user):
    from app.catalog.registered_models.application.delete_alias import delete_alias as action
    return action(db, catalog_name, schema_name, name, alias, user)


async def register_version(db, catalog_name, schema_name, name, body, user):
    from app.catalog.registered_models.application.register_version import register_version as action
    return await action(db, catalog_name, schema_name, name, body, user)


async def invoke_registered_model(db, catalog_name, schema_name, model_name, body):
    from app.catalog.registered_models.application.invoke_registered_model import invoke_registered_model as action
    return await action(db, catalog_name, schema_name, model_name, body)
