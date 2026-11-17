"""File storage: Supabase Storage in production, local disk in development and tests."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

import httpx

from ..config import get_settings


class Storage(Protocol):
    def put(self, path: str, data: bytes, content_type: str) -> None: ...
    def get(self, path: str) -> bytes: ...
    def delete(self, path: str) -> None: ...


class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _full(self, path: str) -> Path:
        full = (self.root / path).resolve()
        if self.root not in full.parents:
            raise ValueError("invalid storage path")
        return full

    def put(self, path: str, data: bytes, content_type: str) -> None:
        full = self._full(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(data)

    def get(self, path: str) -> bytes:
        return self._full(path).read_bytes()

    def delete(self, path: str) -> None:
        full = self._full(path)
        if full.exists():
            os.remove(full)


class SupabaseStorage:
    def __init__(self, url: str, service_key: str, bucket: str):
        self.base = f"{url.rstrip('/')}/storage/v1/object"
        self.bucket = bucket
        self.headers = {"Authorization": f"Bearer {service_key}", "apikey": service_key}

    def _url(self, path: str) -> str:
        return f"{self.base}/{self.bucket}/{quote(path)}"

    def put(self, path: str, data: bytes, content_type: str) -> None:
        r = httpx.post(
            self._url(path),
            content=data,
            headers={**self.headers, "Content-Type": content_type or "application/octet-stream", "x-upsert": "true"},
            timeout=120,
        )
        r.raise_for_status()

    def get(self, path: str) -> bytes:
        r = httpx.get(self._url(path), headers=self.headers, timeout=120)
        r.raise_for_status()
        return r.content

    def delete(self, path: str) -> None:
        httpx.request(
            "DELETE", f"{self.base}/{self.bucket}", json={"prefixes": [path]}, headers=self.headers, timeout=30
        )


@lru_cache
def get_storage() -> Storage:
    s = get_settings()
    if s.storage_backend == "supabase":
        if not (s.supabase_url and s.supabase_service_role_key):
            raise RuntimeError("STORAGE_BACKEND=supabase requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
        return SupabaseStorage(s.supabase_url, s.supabase_service_role_key, s.supabase_storage_bucket)
    return LocalStorage(s.local_storage_dir)
