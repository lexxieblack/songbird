from songbird.models.exception import SongbirdException


class UserBanAlreadyExistsError(SongbirdException):
    default_message = "User ban already exists"


class UserBanNotFoundError(SongbirdException):
    default_message = "User ban not found"


class GuildBanAlreadyExistsError(SongbirdException):
    default_message = "Guild ban already exists"


class GuildBanNotFoundError(SongbirdException):
    default_message = "Guild ban not found"


class BlackwallAlreadyExistsError(SongbirdException):
    default_message = "Blackwall config already exists for this guild"


class BlackwallNotFoundError(SongbirdException):
    default_message = "Blackwall config not found for this guild"
