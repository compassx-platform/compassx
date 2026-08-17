"""Pydantic models for storage backends and volume operations."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class StorageProvider(str, Enum):
    AZURE = "azure"
    S3 = "s3"
    MINIO = "minio"


class AzureCredentials(BaseModel):
    account_name: str
    container: str
    base_path: str = "compassx/"
    account_key: Optional[str] = None
    tenant_id: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None


class S3Credentials(BaseModel):
    bucket: str
    base_path: str = "compassx/"
    region: str = "us-east-1"
    access_key: str
    secret_key: str
    endpoint_url: Optional[str] = None


class StorageBackendCreate(BaseModel):
    name: str
    provider: StorageProvider
    is_default: bool = False
    azure: Optional[AzureCredentials] = None
    s3: Optional[S3Credentials] = None


class StorageBackendRead(BaseModel):
    id: str
    name: str
    provider: StorageProvider
    is_default: bool
    container_or_bucket: str
    base_path: str
    created_at: datetime


class FileInfo(BaseModel):
    file_path: str
    file_name: str
    size_bytes: int
    content_type: Optional[str]
    last_modified: datetime


class VolumeFileCreate(BaseModel):
    """Internal model for indexing uploaded files."""
    volume_id: str
    file_path: str
    file_name: str
    size_bytes: int
    content_type: Optional[str]
    uploaded_by: str
