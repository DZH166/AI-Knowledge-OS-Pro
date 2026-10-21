from __future__ import annotations

import json
from urllib import request
from urllib.error import HTTPError, URLError


BASE_URL = "http://127.0.0.1:8000"


def call(method: str, path: str) -> tuple[int, dict]:
    req = request.Request(f"{BASE_URL}{path}", method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with request.urlopen(req, timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8")
        return exc.code, json.loads(body) if body else {}
    except URLError as exc:
        raise SystemExit(f"Backend is not reachable at {BASE_URL}: {exc}") from exc


def main() -> None:
    checks = [
        ("GET", "/health"),
        ("GET", "/api/system/status"),
        ("POST", "/api/system/test-qdrant"),
        ("POST", "/api/system/test-embedding"),
        ("POST", "/api/system/test-llm"),
    ]
    for method, path in checks:
        status, data = call(method, path)
        print(f"{method} {path} -> {status}")
        print(json.dumps(data, ensure_ascii=False, indent=2)[:1200])


if __name__ == "__main__":
    main()
