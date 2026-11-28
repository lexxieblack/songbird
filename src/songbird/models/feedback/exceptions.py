from songbird.models.exception import SongbirdException


class ThreadAlreadyExistsError(SongbirdException):
    default_message = "Thread already exists"


class ThreadNotFoundError(SongbirdException):
    default_message = "Thread not found"


class NotForumChannel(SongbirdException):
    default_message = "Not a forum channel"
