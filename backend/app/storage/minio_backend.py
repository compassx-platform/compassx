"""MinIO backend — S3-compatible, just forces endpoint_url."""
from .s3_backend import S3StorageBackend


class MinIOStorageBackend(S3StorageBackend):
    def __init__(
        self,
        bucket: str,
        base_path: str,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
    ):
        super().__init__(
            bucket=bucket,
            base_path=base_path,
            region="us-east-1",  # MinIO ignores region, but boto3 requires it
            access_key=access_key,
            secret_key=secret_key,
            endpoint_url=endpoint_url,
        )
