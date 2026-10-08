from __future__ import annotations


def test_healthz_endpoint(client):
    """GET /api/healthz is an alias of GET /api/health with identical keys and 200 status."""
    resp_healthz = client.get("/api/healthz")
    resp_health = client.get("/api/health")

    assert resp_healthz.status_code == 200
    assert resp_health.status_code == 200

    data_z = resp_healthz.json()
    data_h = resp_health.json()

    assert set(data_z.keys()) == set(data_h.keys())
    assert data_z == data_h
