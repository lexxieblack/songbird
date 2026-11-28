from songbird.models.exception import SongbirdException


class UserInfoAlreadyExistsError(SongbirdException):
    default_message = "User info already exists"


class UserInfoNotFoundError(SongbirdException):
    default_message = "User info not found"


class MessageAlreadyExistsError(SongbirdException):
    default_message = "Message already exists"
