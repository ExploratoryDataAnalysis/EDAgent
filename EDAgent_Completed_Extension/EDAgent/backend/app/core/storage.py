"""
Storage Abstraction Layer
Provides a uniform interface for local disk and S3-compatible object storage.
"""

from abc import ABC, abstractmethod
import os
import shutil
from typing import BinaryIO, Optional


class StorageProvider(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    async def save_file(self, file_obj: BinaryIO, destination_path: str) -> str:
        """Saves a file stream to the destination and returns the storage URI."""
        pass

    @abstractmethod
    async def get_file_path(self, storage_uri: str) -> str:
        """Resolves a storage URI to a local file path for computation."""
        pass

    @abstractmethod
    async def delete_file(self, storage_uri: str) -> bool:
        """Deletes a file from storage."""
        pass

    @abstractmethod
    async def file_exists(self, storage_uri: str) -> bool:
        """Checks if a file exists."""
        pass


class LocalStorageProvider(StorageProvider):
    """Local filesystem storage implementation for development and single-node setups."""

    def __init__(self, base_dir: str = "./data/uploads"):
        self.base_dir = os.path.abspath(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)

    async def save_file(self, file_obj: BinaryIO, destination_path: str) -> str:
        full_path = os.path.join(self.base_dir, destination_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as buffer:
            shutil.copyfileobj(file_obj, buffer)
        return full_path

    async def get_file_path(self, storage_uri: str) -> str:
        if os.path.exists(storage_uri):
            return storage_uri
        full_path = os.path.join(self.base_dir, storage_uri)
        if os.path.exists(full_path):
            return full_path
        raise FileNotFoundError(f"File not found at: {storage_uri}")

    async def delete_file(self, storage_uri: str) -> bool:
        try:
            path = await self.get_file_path(storage_uri)
            if os.path.exists(path):
                os.remove(path)
                parent_dir = os.path.dirname(path)
                # Clean up empty parent directory (dataset isolation folder) if empty
                if os.path.exists(parent_dir) and not os.listdir(parent_dir):
                    shutil.rmtree(parent_dir, ignore_errors=True)
                return True
        except FileNotFoundError:
            return False
        return False

    async def delete_dataset_directory(self, destination_subpath: str) -> bool:
        """Deletes the entire isolated dataset folder."""
        full_path = os.path.join(self.base_dir, destination_subpath)
        if os.path.exists(full_path) and os.path.isdir(full_path):
            shutil.rmtree(full_path, ignore_errors=True)
            return True
        return False

    async def file_exists(self, storage_uri: str) -> bool:
        try:
            path = await self.get_file_path(storage_uri)
            return os.path.exists(path)
        except FileNotFoundError:
            return False


def get_storage_provider() -> StorageProvider:
    """Factory to retrieve configured storage provider."""
    from app.core.config import settings
    if settings.STORAGE_BACKEND != "local":
        # Object-store backends are not implemented; failing loudly beats silently using local disk.
        raise RuntimeError(f"Unsupported STORAGE_BACKEND '{settings.STORAGE_BACKEND}'. Only 'local' is implemented.")
    return LocalStorageProvider(base_dir=settings.LOCAL_STORAGE_PATH)
