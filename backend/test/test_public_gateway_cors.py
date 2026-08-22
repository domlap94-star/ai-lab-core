from fastapi.testclient import TestClient

from app.main import app


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def preflight(client: TestClient, origin: str):
    return client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )


def main() -> None:
    client = TestClient(app)

    public_gateway = preflight(client, "http://127.0.0.1:8789")
    require(public_gateway.status_code == 200, public_gateway.text)
    require(
        public_gateway.headers.get("access-control-allow-origin")
        == "http://127.0.0.1:8789",
        "public gateway origin was not returned exactly",
    )

    arbitrary_lan = preflight(client, "http://192.168.1.10:8789")
    require(arbitrary_lan.status_code == 400, "arbitrary LAN origin was allowed")
    require(
        "access-control-allow-origin" not in arbitrary_lan.headers,
        "rejected origin received an allow-origin header",
    )

    print("PUBLIC_GATEWAY_CORS=PASS")
    print("ARBITRARY_LAN_CORS=REJECTED")


if __name__ == "__main__":
    main()
