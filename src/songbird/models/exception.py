from typing import Any


class SongbirdException(Exception):
    default_message: str = ""

    def __init__(self, message: str | None = None, data: dict[str, Any] | None = None) -> None:
        super().__init__(message or self.default_message)
        self._data = data or {}

    @property
    def data(self) -> dict[str, Any]:
        return self._data
