from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from songbird.models.exception import SongbirdException
from songbird.models.feedback.exceptions import NotForumChannel, ThreadAlreadyExistsError, ThreadNotFoundError
from songbird.models.feedback.thread import Thread, thread_table

NOW = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def test_feedback_tables_live_in_the_feedback_schema() -> None:
    assert thread_table.metadata.schema == "feedback"
    assert thread_table.fullname == "feedback.thread"


def test_thread_table_columns_and_primary_key() -> None:
    assert set(thread_table.columns.keys()) == {"user_id", "thread_id", "created_at"}
    assert list(thread_table.primary_key.columns.keys()) == ["user_id"]
    assert thread_table.c.created_at.nullable is False


def test_thread_reads_attributes() -> None:
    thread = Thread.model_validate({"user_id": 1, "thread_id": 2, "created_at": NOW})

    assert thread.user_id == 1
    assert thread.thread_id == 2


@pytest.mark.parametrize(
    ("error_type", "default_message"),
    [
        (ThreadAlreadyExistsError, "Thread already exists"),
        (ThreadNotFoundError, "Thread not found"),
        (NotForumChannel, "Not a forum channel"),
    ],
)
def test_feedback_exceptions_have_default_messages(error_type: Callable[[], SongbirdException], default_message: str) -> None:
    error = error_type()

    assert str(error) == default_message
    assert error.data == {}


def test_feedback_exceptions_accept_a_custom_message_and_data() -> None:
    error = NotForumChannel("wrong channel", {"channel_id": 3})

    assert str(error) == "wrong channel"
    assert error.data == {"channel_id": 3}
