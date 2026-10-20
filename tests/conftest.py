import os
import sys
from pathlib import Path

import psycopg
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # let the tests import scheduler, agent, api and evals

TEST_DB_NAME = "sched_test"


def read_env_file():
    values = {}
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return values


def admin_url():
    """DATABASE_URL if set (CI), otherwise built from .env (Postgres is on port 5434 on your computer)."""
    if os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    env = read_env_file()
    if "POSTGRES_PASSWORD" not in env:
        raise RuntimeError("no DATABASE_URL and no .env file")
    return f"postgresql://{env['POSTGRES_USER']}:{env['POSTGRES_PASSWORD']}@localhost:5434/{env['POSTGRES_DB']}"


@pytest.fixture(scope="session")
def database_url():
    """A fresh test database, so the tests never touch real data."""
    try:
        admin = psycopg.connect(admin_url(), autocommit=True)
    except (psycopg.OperationalError, RuntimeError):
        pytest.skip("no database available (start it with: docker compose up -d postgres)")

    admin.execute(f"DROP DATABASE IF EXISTS {TEST_DB_NAME} WITH (FORCE)")
    admin.execute(f"CREATE DATABASE {TEST_DB_NAME}")
    admin.close()

    url = admin_url().rsplit("/", 1)[0] + "/" + TEST_DB_NAME
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute((ROOT / "db" / "init.sql").read_text(encoding="utf-8"))
    return url


@pytest.fixture
def clean_tables(database_url):
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("TRUNCATE committed_plans, audit_log RESTART IDENTITY")
    return database_url


@pytest.fixture(autouse=True)
def no_real_llm_keys(monkeypatch):
    """The tests must never call a real model."""
    for name in ["GROQ_API_KEY", "OLLAMA_URL"]:
        monkeypatch.delenv(name, raising=False)
