from typing import Protocol


class StorageProvider(Protocol):
    def upload(self, path: str, content: bytes, mime_type: str) -> str:
        """Store content and return its provider path."""

    def delete(self, path: str) -> None:
        """Delete content at a provider path."""

    def get_url(self, path: str) -> str:
        """Return a URL for a stored object."""
