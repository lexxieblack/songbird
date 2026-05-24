from typing import Any

from songbird.models.exception import SongbirdException


class UserInfoAlreadyExistsError(SongbirdException):
    def __init__(self, message: str | None = None, data: dict[str, Any] | None = None) -> None:
        super().__init__(message or "User info already exists", data)


class UserInfoNotFoundError(SongbirdException):
    def __init__(self, message: str | None = None, data: dict[str, Any] | None = None) -> None:
        super().__init__(message or "User info not found", data)


class MessageAlreadyExistsError(SongbirdException):
    def __init__(self, message: str | None = None, data: dict[str, Any] | None = None) -> None:
        super().__init__(message or "Message already exists", data)
