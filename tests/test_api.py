from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def valid_payload():
    return {
        "asset_name": "Toyota Corolla",
        "asset_price": 100000,
        "down_payment": 20000,
        "hp_period_months": 60,
        "hp_interest_rate": 5.5,
        "lease_period_months": 60,
        "lease_monthly_payment": 1800,
    }


def test_root_endpoint():
    response = client.get("/")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "success"


def test_analyze_endpoint_success():
    response = client.post(
        "/analyze",
        json=valid_payload(),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "success"
    assert "analysis" in data


def test_analyze_returns_financial_options():
    response = client.post(
        "/analyze",
        json=valid_payload(),
    )

    data = response.json()
    analysis = data["analysis"]

    assert "cash_purchase" in analysis
    assert "hire_purchase" in analysis
    assert "leasing" in analysis
    assert "comparison" in analysis


def test_analyze_calculates_financed_amount():
    response = client.post(
        "/analyze",
        json=valid_payload(),
    )

    data = response.json()
    analysis = data["analysis"]

    assert analysis["financed_amount"] == 80000


def test_analyze_rejects_invalid_down_payment():
    payload = valid_payload()
    payload["down_payment"] = 120000

    response = client.post(
        "/analyze",
        json=payload,
    )

    assert response.status_code == 422


def test_analyze_rejects_invalid_asset_price():
    payload = valid_payload()
    payload["asset_price"] = 0

    response = client.post(
        "/analyze",
        json=payload,
    )

    assert response.status_code == 422


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_analyze_document_rejects_non_pdf():
    files = {"file": ("test.txt", b"some plain text", "text/plain")}
    response = client.post("/analyze-document", files=files)
    assert response.status_code == 415


def test_analyze_document_rejects_empty_file():
    files = {"file": ("empty.pdf", b"", "application/pdf")}
    response = client.post("/analyze-document", files=files)
    assert response.status_code == 400


def test_analyze_document_accepts_pdf():
    # Minimal PDF structure
    minimal_pdf = (
        b"%PDF-1.0\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj "
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
        b"3 0 obj<</Type/Page/MediaBox[0 0 3 3]>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n"
        b"0000000058 00000 n \n0000000115 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"
    )
    files = {"file": ("quote.pdf", minimal_pdf, "application/pdf")}
    response = client.post("/analyze-document", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "extraction" in data
    assert "user_action_required" in data


def test_dashboard_static_mount():
    """Verify that Phase 4 frontend dashboard is properly mounted and served."""
    response = client.get("/dashboard/")
    assert response.status_code == 200
    assert "Virtual CFO Committee" in response.text
    assert "cfo-form" in response.text

    css_response = client.get("/dashboard/styles.css")
    assert css_response.status_code == 200

    js_response = client.get("/dashboard/app.js")
    assert js_response.status_code == 200


def test_analyze_with_cash_discount_and_rate_type():
    """Verify that /analyze accepts Phase 4 cash_discount and hp_rate_type parameters."""
    payload = valid_payload()
    payload["cash_discount"] = 5000
    payload["hp_rate_type"] = "fixed"

    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    analysis = data["analysis"]
    assert analysis["validation_passed"] is True
    assert analysis["cash_purchase"]["total_cash_cost"] == 95000


def test_analyze_legal_rejection_high_eir():
    """Verify that /analyze returns validation_passed=False when EIR exceeds statutory cap."""
    payload = valid_payload()
    payload["hp_interest_rate"] = 22.0  # Exceeds BNM 17% cap

    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    analysis = data["analysis"]
    assert analysis["validation_passed"] is False
    assert len(analysis["validation_errors"]) > 0
    assert any("EIR" in err or "cap" in err.lower() for err in analysis["validation_errors"])


def test_analyze_legal_rejection_low_deposit():
    """Verify that /analyze returns validation_passed=False when deposit is under 10% statutory min."""
    payload = valid_payload()
    payload["down_payment"] = 5000  # 5% < 10% statutory requirement on 100k asset

    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    analysis = data["analysis"]
    assert analysis["validation_passed"] is False
    assert len(analysis["validation_errors"]) > 0
    assert any("10%" in err or "deposit" in err.lower() for err in analysis["validation_errors"])
