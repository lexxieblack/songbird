from typing import Any

from songbird.models.exception import SongbirdException


class UserBanAlreadyExistsError(SongbirdException):
    def __init__(self, message: str | None = None, data: dict[str, Any] | None = None) -> None:
        super().__init__(message or "User ban already exists", data)


class UserBanNotFoundError(SongbirdException):
    def __init__(self, message: str | None = None, data: dict[str, Any] | None = None) -> None:
        super().__init__(message or "User ban not found", data)


class GuildBanAlreadyExistsError(SongbirdException):
    def __init__(self, message: str | None = None, data: dict[str, Any] | None = None) -> None:
        super().__init__(message or "Guild ban already exists", data)


class GuildBanNotFoundError(SongbirdException):
    def __init__(self, message: str | None = None, data: dict[str, Any] | None = None) -> None:
        super().__init__(message or "Guild ban not found", data)
