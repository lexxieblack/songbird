from uuid import RFC_4122, UUID

from songbird.utils.id_factory import make_id


def test_make_id_returns_a_uuid() -> None:
    assert isinstance(make_id(), UUID)


def test_make_id_is_uuid_version_7() -> None:
    generated = make_id()

    assert generated.version == 7
    assert generated.variant == RFC_4122


def test_make_id_returns_distinct_ids() -> None:
    assert len({make_id() for _ in range(100)}) == 100
