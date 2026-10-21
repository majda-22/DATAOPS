import pytest

from tests.integration.test_metadata_queries import _create_test_engine


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://USER:secret@localhost/test_db",
        "postgresql://tester:PASSWORD@localhost/test_db",
        "postgresql://tester:secret@localhost/YOUR_TEST_DB",
    ],
)
def test_example_database_settings_are_rejected_without_connecting(url):
    with pytest.raises(ValueError, match="still contains example values"):
        _create_test_engine(url, "TEST_DATABASE_URL")


def test_non_postgresql_database_is_rejected():
    with pytest.raises(ValueError, match="must point to PostgreSQL"):
        _create_test_engine("sqlite://", "TEST_DATABASE_URL")


def test_plain_postgresql_url_uses_installed_psycopg_driver():
    engine = _create_test_engine(
        "postgresql://tester:secret@127.0.0.1/test_db", "TEST_DATABASE_URL"
    )
    try:
        assert engine.url.drivername == "postgresql+psycopg"
        assert engine.dialect.create_connect_args(engine.url)[1]["dbname"] == "test_db"
    finally:
        engine.dispose()
