from typing import Any


class SongbirdException(Exception):
    def __init__(self, message: str, data: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self._data = data or {}

    @property
    def data(self) -> dict[str, Any]:
        return self._data
