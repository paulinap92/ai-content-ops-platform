"""Test credentials never fall through to a developer configuration."""
import os
from sqlalchemy.engine import make_url
import pytest
url=os.getenv("CC_SQL_TEST_DATABASE_URL") or os.getenv("CC_SQL_TEST_URL")
if url:
 p=make_url(url)
 if p.host not in {"jobdb","localhost","127.0.0.1","::1"} or p.database!="canarias_cerca_jobs_test":
  raise pytest.UsageError("Disposable PostgreSQL required")
 os.environ["SITE_DATABASE_URL"]=url
 os.environ["EDITOR_DATABASE_URL"]=url
else:
 os.environ["SITE_DATABASE_URL"]="postgresql://unused:unused@127.0.0.1:9/cc_test_not_configured"
 os.environ["EDITOR_DATABASE_URL"]=os.environ["SITE_DATABASE_URL"]
os.environ["EDITOR_TOKEN"]="isolated-editor-test-credential-1234567890"
os.environ["OPENAI_API_KEY"]="isolated-test-no-real-provider-calls"
