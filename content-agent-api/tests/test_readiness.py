from fastapi.testclient import TestClient
from app import create_app


def test_unconfigured_editor_reports_not_ready_without_exposing_configuration():
    client=TestClient(create_app())
    response=client.get('/health/ready')
    assert response.status_code==503
    assert response.json()=={'status':'not_ready'}
    assert client.get('/health/live').status_code==200
    assert client.get('/site/api/options').status_code==401
