def test_response_includes_security_headers(client):
    response = client.get("/auth/google/login", follow_redirects=False)

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["x-frame-options"] == "DENY"
