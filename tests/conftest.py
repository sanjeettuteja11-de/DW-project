import shutil
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from src import pipeline
from src.config import PROJECT_ROOT, Paths
from tests.synthetic import generate


def build_project(root: Path, **kwargs) -> tuple[Paths, int]:
    paths = Paths(root=root, mappings=PROJECT_ROOT / "mappings")
    if not (paths.raw / "matches.csv").exists():
        generate(paths.raw)
    code = pipeline.run(paths, source_url="synthetic-test", expected_franchises=4, **kwargs)
    return paths, code


@pytest.fixture(scope="session")
def built(tmp_path_factory):
    paths, code = build_project(tmp_path_factory.mktemp("project"))
    return paths, code


@pytest.fixture
def db(built):
    paths, _ = built
    conn = sqlite3.connect(paths.db)
    yield conn
    conn.close()


@pytest.fixture
def db_copy(built, tmp_path):
    """A disposable copy of the warehouse for corruption tests."""
    paths, _ = built
    dst = tmp_path / "copy.sqlite"
    shutil.copy(paths.db, dst)
    conn = sqlite3.connect(dst)
    yield conn
    conn.close()


def read(paths: Paths, name: str) -> pd.DataFrame:
    return pd.read_csv(paths.export / f"{name}.csv")
