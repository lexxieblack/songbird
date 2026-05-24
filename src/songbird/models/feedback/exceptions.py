from typing import Any

from songbird.models.exception import SongbirdException


class ThreadAlreadyExistsError(SongbirdException):
    def __init__(self, message: str | None = None, data: dict[str, Any] | None = None) -> None:
        super().__init__(message or "Thread already exists", data)


class ThreadNotFoundError(SongbirdException):
    def __init__(self, message: str | None = None, data: dict[str, Any] | None = None) -> None:
        super().__init__(message or "Thread not found", data)


class NotForumChannel(SongbirdException):
    def __init__(self, message: str | None = None, data: dict[str, Any] | None = None) -> None:
        super().__init__(message or "Not a forum channel", data)
