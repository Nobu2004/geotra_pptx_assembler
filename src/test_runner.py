"""Utility helpers to execute the project's pytest suite programmatically."""

from __future__ import annotations

from typing import Optional, Sequence

import pytest

# Default arguments mirror the ones used by the repository's CI configuration.
DEFAULT_PYTEST_ARGS: tuple[str, ...] = ("-q",)


def run_tests(args: Optional[Sequence[str]] = None) -> int:
    """Run pytest with the provided ``args`` and return the exit code.

    Parameters
    ----------
    args:
        Optional sequence of additional command line arguments that should be
        forwarded to :func:`pytest.main`. When ``None`` the function defaults to
        ``('-q',)`` which provides concise test output suitable for CI logs.
    """

    pytest_args = list(args) if args is not None else list(DEFAULT_PYTEST_ARGS)
    return pytest.main(pytest_args)


def run_default() -> int:
    """Convenience wrapper that runs pytest with the default arguments."""

    return run_tests()


if __name__ == "__main__":  # pragma: no cover - manual execution utility
    raise SystemExit(run_default())
