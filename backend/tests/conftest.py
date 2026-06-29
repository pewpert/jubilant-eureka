"""Shared pytest fixtures: paths to saved HTML snapshots."""
import pathlib
import pytest

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture
def homes_html() -> str:
    return _read("homes_nakano.html")


@pytest.fixture
def chintai_html() -> str:
    return _read("chintai_nakano.html")


@pytest.fixture
def suumo_html() -> str:
    return _read("suumo_firecrawl.html")


@pytest.fixture
def ehousing_html() -> str:
    return _read("ehousing_rent.html")
