import os
from collections.abc import Callable
from typing import Any, Literal, TypeVar, overload

T = TypeVar("T")


@overload
def load_from_env[T](env_var: str, allow_none: Literal[True], return_type: type[T]) -> T | None: ...


@overload
def load_from_env[T](env_var: str, allow_none: Literal[False], return_type: type[T]) -> T: ...


@overload
def load_from_env(env_var: str, allow_none: Literal[True]) -> str | None: ...


@overload
def load_from_env(env_var: str, allow_none: Literal[False] = False) -> str: ...


def load_from_env(
    env_var: str,
    allow_none: bool = False,
    return_type: Callable[[str], Any] = str,
    default: Any = None,
) -> Any:
    val = os.getenv(env_var, default)

    if val is None:
        if allow_none:
            return None
        raise ValueError(f"Environment variable '{env_var}' is missing.")

    try:
        return return_type(val)
    except ValueError as e:
        raise ValueError(f"Could not convert '{val}' to {return_type.__name__}") from e
