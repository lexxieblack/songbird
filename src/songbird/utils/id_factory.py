from typing import cast
from uuid import UUID

from uuid_extensions import uuid7


def make_id() -> UUID:
    return cast(UUID, uuid7())
