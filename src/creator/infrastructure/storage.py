from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from creator.config import Settings
from creator.services.storage.provider import (
    SUPPORTED_STORAGE_MIME_TYPES,
    StorageConfigurationError,
    StorageDeleteError,
    StorageObjectNotFoundError,
    StorageProvider,
    StorageUploadError,
    StorageUrlError,
    StorageValidationError,
    StoredObject,
    StoredObjectMetadata,
    UploadObjectRequest,
)

UrlOpen = Callable[[Request, float], Any]


def _urlopen(request: Request, timeout: float) -> Any:
    return urlopen(request, timeout=timeout)


def _coerce_size_bytes(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def validate_upload_request(request: UploadObjectRequest, *, max_object_bytes: int) -> str:
    if request.mime_type not in SUPPORTED_STORAGE_MIME_TYPES:
        raise StorageValidationError("Unsupported image MIME type")
    if not request.content:
        raise StorageValidationError("Object content is empty")
    if len(request.content) > max_object_bytes:
        raise StorageValidationError("Object content exceeds configured size limit")
    if request.path.startswith("/") or "\\" in request.path or ".." in request.path.split("/"):
        raise StorageValidationError("Invalid object path")

    checksum_sha256 = hashlib.sha256(request.content).hexdigest()
    if request.checksum_sha256 and request.checksum_sha256 != checksum_sha256:
        raise StorageValidationError("Object checksum does not match content")
    return checksum_sha256


class SupabaseStorageProvider:
    def __init__(self, settings: Settings, opener: UrlOpen | None = None) -> None:
        self._settings = settings
        self._opener = opener or _urlopen

    def upload(self, request: UploadObjectRequest) -> StoredObject:
        checksum_sha256 = validate_upload_request(
            request, max_object_bytes=self._settings.storage_max_object_bytes
        )
        self._require_settings()
        try:
            http_request = Request(
                self._object_url(request.path),
                data=request.content,
                headers={
                    "apikey": self._service_role_key,
                    "Authorization": f"Bearer {self._service_role_key}",
                    "Content-Type": request.mime_type,
                    "cache-control": "31536000, immutable",
                    "x-upsert": "false",
                },
                method="POST",
            )
            response = self._opener(http_request, self._settings.supabase_auth_timeout_seconds)
            status_code = int(getattr(response, "status", 200))
            if status_code >= 400:
                raise StorageUploadError("Supabase Storage upload failed")
        except HTTPError as error:
            raise StorageUploadError("Supabase Storage upload failed") from error
        except (TimeoutError, URLError) as error:
            raise StorageUploadError("Supabase Storage upload failed") from error

        return StoredObject(
            path=request.path,
            url=self.get_url(request.path),
            mime_type=request.mime_type,
            size_bytes=len(request.content),
            checksum_sha256=checksum_sha256,
            metadata={"provider": "supabase", **request.metadata},
        )

    def delete(self, path: str) -> None:
        self._require_settings()
        try:
            http_request = Request(
                self._object_url(path),
                headers={
                    "apikey": self._service_role_key,
                    "Authorization": f"Bearer {self._service_role_key}",
                },
                method="DELETE",
            )
            response = self._opener(http_request, self._settings.supabase_auth_timeout_seconds)
            status_code = int(getattr(response, "status", 200))
            if status_code >= 400:
                raise StorageDeleteError("Supabase Storage delete failed")
        except HTTPError as error:
            raise StorageDeleteError("Supabase Storage delete failed") from error
        except (TimeoutError, URLError) as error:
            raise StorageDeleteError("Supabase Storage delete failed") from error

    def stat(self, path: str) -> StoredObjectMetadata:
        self._require_settings()
        try:
            http_request = Request(
                self._object_info_url(path),
                headers={
                    "apikey": self._service_role_key,
                    "Authorization": f"Bearer {self._service_role_key}",
                    "Accept": "application/json",
                },
                method="GET",
            )
            response = self._opener(http_request, self._settings.supabase_auth_timeout_seconds)
            status_code = int(getattr(response, "status", 200))
            response_body = bytes(response.read())
            if status_code == 404:
                raise StorageObjectNotFoundError("Supabase Storage object does not exist")
            if status_code >= 400:
                raise StorageUrlError("Supabase Storage object metadata request failed")
        except HTTPError as error:
            if error.code == 404:
                raise StorageObjectNotFoundError(
                    "Supabase Storage object does not exist"
                ) from error
            raise StorageUrlError("Supabase Storage object metadata request failed") from error
        except (TimeoutError, URLError) as error:
            raise StorageUrlError("Supabase Storage object metadata request failed") from error

        try:
            payload = json.loads(response_body.decode("utf-8")) if response_body else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise StorageUrlError("Supabase Storage returned invalid metadata response") from error
        if not isinstance(payload, dict):
            raise StorageUrlError("Supabase Storage returned invalid metadata response")
        raw_metadata = payload.get("metadata")
        metadata: dict[str, object] = (
            {str(key): value for key, value in raw_metadata.items()}
            if isinstance(raw_metadata, dict)
            else {}
        )
        mimetype = payload.get("mimetype") or payload.get("mime_type") or metadata.get("mimetype")
        raw_size: object = payload.get("size")
        if raw_size is None:
            raw_size = metadata.get("size", 0)
        size_bytes = _coerce_size_bytes(raw_size)
        checksum = metadata.get("checksum_sha256")
        return StoredObjectMetadata(
            path=path,
            mime_type=str(mimetype or "application/octet-stream"),
            size_bytes=size_bytes,
            checksum_sha256=str(checksum) if checksum else None,
            metadata=metadata,
        )

    def get_url(self, path: str) -> str:
        self._require_settings()
        body = json.dumps({"expiresIn": self._settings.storage_signed_url_expires_seconds}).encode(
            "utf-8"
        )
        try:
            http_request = Request(
                self._signed_url_endpoint(path),
                data=body,
                headers={
                    "apikey": self._service_role_key,
                    "Authorization": f"Bearer {self._service_role_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                method="POST",
            )
            response = self._opener(http_request, self._settings.supabase_auth_timeout_seconds)
            status_code = int(getattr(response, "status", 200))
            response_body = bytes(response.read())
            if status_code >= 400:
                raise StorageUrlError("Supabase Storage signed URL request failed")
        except HTTPError as error:
            raise StorageUrlError("Supabase Storage signed URL request failed") from error
        except (TimeoutError, URLError) as error:
            raise StorageUrlError("Supabase Storage signed URL request failed") from error

        try:
            payload = json.loads(response_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise StorageUrlError(
                "Supabase Storage returned invalid signed URL response"
            ) from error
        if not isinstance(payload, dict):
            raise StorageUrlError("Supabase Storage returned invalid signed URL response")
        signed_url = payload.get("signedURL") or payload.get("signedUrl")
        if not isinstance(signed_url, str) or not signed_url:
            raise StorageUrlError("Supabase Storage did not return a signed URL")
        if signed_url.startswith("http"):
            return signed_url
        return f"{self._storage_url}{signed_url}"

    def _require_settings(self) -> None:
        if not self._settings.supabase_url:
            raise StorageConfigurationError("SUPABASE_URL is required for Supabase Storage")
        if not self._settings.supabase_service_role_key:
            raise StorageConfigurationError(
                "SUPABASE_SERVICE_ROLE_KEY is required for Supabase Storage"
            )

    @property
    def _storage_url(self) -> str:
        if not self._settings.supabase_url:
            raise StorageConfigurationError("SUPABASE_URL is required for Supabase Storage")
        return f"{self._settings.supabase_url.rstrip('/')}/storage/v1"

    @property
    def _service_role_key(self) -> str:
        service_role_key = self._settings.supabase_service_role_key
        if not service_role_key:
            raise StorageConfigurationError(
                "SUPABASE_SERVICE_ROLE_KEY is required for Supabase Storage"
            )
        return service_role_key

    def _object_url(self, path: str) -> str:
        quoted_path = quote(path, safe="/")
        return f"{self._storage_url}/object/{self._settings.storage_bucket}/{quoted_path}"

    def _signed_url_endpoint(self, path: str) -> str:
        quoted_path = quote(path, safe="/")
        return f"{self._storage_url}/object/sign/{self._settings.storage_bucket}/{quoted_path}"

    def _object_info_url(self, path: str) -> str:
        quoted_path = quote(path, safe="/")
        return f"{self._storage_url}/object/info/{self._settings.storage_bucket}/{quoted_path}"


class LocalStorageProvider:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._root = Path(settings.local_storage_root).resolve()

    def upload(self, request: UploadObjectRequest) -> StoredObject:
        checksum_sha256 = validate_upload_request(
            request, max_object_bytes=self._settings.storage_max_object_bytes
        )
        target = self._target_path(request.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            if target.exists():
                raise StorageUploadError("Local storage object already exists")
            target.write_bytes(request.content)
        except OSError as error:
            raise StorageUploadError("Local storage upload failed") from error
        return StoredObject(
            path=request.path,
            url=target.as_uri(),
            mime_type=request.mime_type,
            size_bytes=len(request.content),
            checksum_sha256=checksum_sha256,
            metadata={"provider": "local", **request.metadata},
        )

    def delete(self, path: str) -> None:
        target = self._target_path(path)
        try:
            target.unlink(missing_ok=True)
        except OSError as error:
            raise StorageDeleteError("Local storage delete failed") from error

    def get_url(self, path: str) -> str:
        target = self._target_path(path)
        if not target.exists():
            raise StorageUrlError("Local storage object does not exist")
        return target.as_uri()

    def stat(self, path: str) -> StoredObjectMetadata:
        target = self._target_path(path)
        if not target.exists():
            raise StorageObjectNotFoundError("Local storage object does not exist")
        try:
            content = target.read_bytes()
        except OSError as error:
            raise StorageUrlError("Local storage object metadata is unavailable") from error
        checksum = hashlib.sha256(content).hexdigest()
        return StoredObjectMetadata(
            path=path,
            mime_type=_mime_type_from_path(path),
            size_bytes=len(content),
            checksum_sha256=checksum,
            metadata={"provider": "local"},
        )

    def _target_path(self, path: str) -> Path:
        validate_upload_request(
            UploadObjectRequest(path=path, content=b"placeholder", mime_type="image/png"),
            max_object_bytes=max(self._settings.storage_max_object_bytes, 1),
        )
        target = (self._root / path).resolve()
        if self._root not in target.parents:
            raise StorageValidationError("Invalid object path")
        return target


def create_storage_provider(settings: Settings) -> StorageProvider:
    match settings.storage_provider:
        case "supabase":
            return SupabaseStorageProvider(settings)
        case "local":
            return LocalStorageProvider(settings)
        case _:
            raise StorageConfigurationError("Unsupported storage provider")


def _mime_type_from_path(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    return "application/octet-stream"
