from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.store.db import ChartConnection
from tests.test_access import access_client as medicine_client  # noqa: F401
from tests.test_access import sign_in

PATH = "/api/chart/patients/patient1/medicines"


def test_explicit_current_use_is_persistent_idempotent_and_separate_from_old_ocr(request):
    client = request.getfixturevalue("medicine_client")
    client.app.state.db.update(
        "record", extraction_json='{"medications":[{"raw_text":"Old drug"}]}'
    )
    sign_in(client, "patient1")
    assert client.get(PATH).json() == {"medicines": []}
    body = {"id": uuid4().hex, "name": "  Fictional medicine ৫ mg  ", "instructions": "½ at night"}
    saved = client.post(PATH, json=body)
    assert saved.status_code == 200
    assert saved.json()["name"] == "Fictional medicine ৫ mg"
    assert saved.json()["instructions"] == "½ at night"
    assert saved.json()["reported_by"] == "patient"
    assert client.post(PATH, json=body).json() == saved.json()
    assert client.post(PATH, json={**body, "name": "Other drug"}).status_code == 409
    client.app.state.chart_digest_tasks = {}  # The list lives in the database, not app state.
    response = client.get(PATH)
    assert response.headers["cache-control"] == "no-store"
    assert len(response.json()["medicines"]) == 1
    assert "Old drug" not in response.text
    assert client.delete(f"{PATH}/{body['id']}").status_code == 200
    assert client.get(PATH).json() == {"medicines": []}


@pytest.mark.parametrize("status", ["pending", "declined", "revoked", "approved"])
def test_doctor_reads_only_with_active_consent_and_cannot_change_patients_list(request, status):
    client = request.getfixturevalue("medicine_client")
    sign_in(client, "patient1")
    body = {"id": uuid4().hex, "name": "Fictional medicine"}
    assert client.post(PATH, json=body).status_code == 200
    with client.app.state.db.session() as session:
        session.add(
            ChartConnection(
                patient_id="patient1",
                doctor_id="doctor",
                status=status,
                requested_at=datetime.now(UTC),
            )
        )
        session.commit()
    sign_in(client, "doctor")
    assert client.get(PATH).status_code == (200 if status == "approved" else 404)
    assert client.post(PATH, json=body).status_code == 403
    assert client.delete(f"{PATH}/{body['id']}").status_code == 403
    sign_in(client, "patient2")
    assert client.get(PATH).status_code == 404
    assert client.post(PATH, json=body).status_code == 404
    assert client.delete(f"{PATH}/{body['id']}").status_code == 404


def test_medicines_validate_identity_and_require_csrf(request):
    client = request.getfixturevalue("medicine_client")
    assert client.get(PATH).status_code == 401
    sign_in(client, "patient1")
    assert client.post(PATH, json={"id": uuid4().hex, "name": "   "}).status_code == 422
    assert client.post(PATH, json={"id": "invalid", "name": "Drug"}).status_code == 422
    client.headers.pop("x-csrf-token")
    assert client.post(PATH, json={"id": uuid4().hex, "name": "Drug"}).status_code == 403
