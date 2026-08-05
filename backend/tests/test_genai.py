import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_parse_order_endpoint_returns_draft_order():
    response = client.post(
        "/api/genai/parse-order",
        json={"text": "buy 10 AAPL at 100"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["requires_confirmation"] is True
    assert payload["draft_order"]["ticker"] == "AAPL"
    assert payload["draft_order"]["side"] == "buy"
    assert payload["draft_order"]["qty"] == 10
    assert payload["draft_order"]["type"] == "limit"


def test_extract_id_endpoint_returns_structured_fields():
    response = client.post(
        "/api/genai/extract-id",
        json={"file_path": "/tmp/sample.pdf", "content_type": "application/pdf"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["extracted_full_name"] is None
    assert payload["extraction_confidence"] is None


def test_market_websocket_emits_snapshot():
    with client.websocket_connect("/ws/market/AAPL") as websocket:
        message = websocket.receive_json()

    assert message["ticker"] == "AAPL"
    assert message["type"] == "snapshot"
    assert "price" in message
