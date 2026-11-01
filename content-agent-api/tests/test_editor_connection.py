from sqlalchemy.engine import make_url
from src.core.document_store import connection_string


def test_editor_uses_direct_neon_connections_and_preserves_tls_parameters():
    parsed = make_url(connection_string("postgresql+psycopg://sample:sample@ep-test-pooler.c-8.eu-central-1.aws.neon.tech/canarias_cerca?sslmode=require&channel_binding=require"))
    assert parsed.host == "ep-test.c-8.eu-central-1.aws.neon.tech"
    assert parsed.query == {"sslmode":"require", "channel_binding":"require"}
    assert parsed.password == "sample"


def test_disposable_or_other_postgres_host_is_preserved():
    assert make_url(connection_string("postgresql://user:pass@jobdb:5432/canarias_cerca_jobs_test")).host == "jobdb"
