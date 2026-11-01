import io

import pytest
from botocore.exceptions import ClientError

from app.store.object_storage import PrivateObjectStorage, StorageError
from tests.test_access import access_client, sign_in  # noqa: F401
from tests.test_combined_submission import approved, recording


class FakeS3:
    def __init__(self):
        self.data = {}

    def put_object(self, **kwargs):
        self.data[kwargs["Key"]] = (kwargs["Body"], kwargs["ContentType"])

    def get_object(self, **kwargs):
        data, mime = self.data[kwargs["Key"]]
        return {"Body": io.BytesIO(data), "ContentType": mime}

    def delete_objects(self, **kwargs):
        for item in kwargs["Delete"]["Objects"]:
            self.data.pop(item["Key"], None)
        return {}

    def head_object(self, **kwargs):
        if kwargs["Key"] not in self.data:
            raise ClientError({"Error": {"Code": "404"}}, "HeadObject")
        return {}


def test_private_files_round_trip_and_delete():
    storage = PrivateObjectStorage(FakeS3(), "private")
    storage.put("record-1", "original", b"image", "image/jpeg")
    storage.put("record-1", "audio", b"audio", "audio/wav")
    assert storage.get("record-1", "audio") == (b"audio", "audio/wav")
    storage.delete_record("record-1")
    with pytest.raises(StorageError):
        storage.get("record-1", "original")
    with pytest.raises(ValueError):
        storage.key("../other", "audio")


def test_saved_files_are_chart_protected_and_deleted(request, monkeypatch):
    client = request.getfixturevalue("access_client")
    storage = PrivateObjectStorage(FakeS3(), "private")
    client.app.state.object_storage = storage
    approved(client)

    async def capture(ctx):
        pass

    monkeypatch.setattr(client.app.state.orchestrator, "execute", capture)
    sign_in(client, "doctor")
    response = client.post(
        "/api/runs",
        data={"patient_id": "patient1", "idempotency_key": "stored"},
        files={
            "image": ("image.jpg", b"image", "image/jpeg"),
            "audio": ("voice.wav", recording(), "audio/wav"),
        },
    )
    assert response.status_code == 200
    run_id = response.json()["run_id"]
    assert client.get(f"/api/runs/{run_id}/files/audio").content == recording()
    storage.put(run_id, "redacted", b"redacted", "image/png")
    client.app.state.object_storage = PrivateObjectStorage(storage.client, "private")
    assert client.get(f"/api/runs/{run_id}").json()["source_available"] is True
    assert client.get(f"/api/runs/{run_id}/files/redacted.png").content == b"redacted"
    sign_in(client, "patient2")
    assert client.get(f"/api/runs/{run_id}/files/original").status_code == 404
    sign_in(client, "patient1")
    assert client.get(f"/api/runs/{run_id}/files/original").content == b"image"
    assert client.post("/api/chart/connections/doctor/revoke").status_code == 200
    sign_in(client, "doctor")
    assert client.get(f"/api/runs/{run_id}/files/audio").status_code == 404
    sign_in(client, "patient1")
    client.app.state.db.update(run_id, status="reviewing")
    assert client.delete(f"/api/chart/records/{run_id}").status_code == 200
    assert not storage.client.data
