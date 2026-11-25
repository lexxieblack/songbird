from typing import cast
from uuid import UUID

from uuid_extensions import uuid7  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]


def make_id() -> UUID:
    return cast(UUID, uuid7())
