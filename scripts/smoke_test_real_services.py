from __future__ import annotations

import argparse
import json
from urllib import request
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit


BASE_URL = "http://127.0.0.1:8000"
REQUIRED_COMPONENTS = ("db", "qdrant", "collection", "redis", "worker", "llm", "embedding")


def call(method: str, path: str, *, base_url: str = BASE_URL, timeout: float = 10) -> tuple[int, object]:
    req = request.Request(f"{base_url}{path}", method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with request.urlopen(req, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        exc.close()
        return exc.code, {}


def validate_reply(path: str, payload: object) -> None:
    if not isinstance(payload, dict):
        raise ValueError("invalid_response_shape")
    if "success" in payload:
        if payload["success"] is not True or payload.get("error") is not None:
            raise ValueError("business_failure")
        payload = payload.get("data")
        if not isinstance(payload, dict):
            raise ValueError("invalid_response_shape")
    if payload.get("ok") is False:
        raise ValueError("business_failure")
    if path == "/health":
        if payload.get("status") != "ok":
            raise ValueError("health_not_ready")
        if payload.get("runtime_mode") != "real":
            raise ValueError("real_mode_not_verified")
    elif path == "/api/system/status":
        runtime = payload.get("runtime")
        if not isinstance(runtime, dict) or runtime.get("runtime_mode") != "real":
            raise ValueError("real_mode_not_verified")
        for name in REQUIRED_COMPONENTS:
            component = payload.get(name)
            if not isinstance(component, dict) or component.get("ok") is not True:
                raise ValueError(f"component_not_ready:{name}")
            if component.get("status") == "demo":
                raise ValueError(f"synthetic_component:{name}")
    elif payload.get("ok") is not True or payload.get("status") != "ready":
        raise ValueError("provider_probe_not_ready")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check real-service readiness without paid provider calls by default.")
    parser.add_argument("--probe-providers", action="store_true", help="Explicitly call embedding and LLM providers; may incur charges.")
    parser.add_argument("--base-url", default=BASE_URL, help="Backend http(s) origin.")
    parser.add_argument("--timeout", type=float, default=10, help="Per-request timeout in seconds (maximum 120).")
    args = parser.parse_args(argv)
    origin = urlsplit(args.base_url)
    if origin.scheme not in {"http", "https"} or not origin.netloc or origin.username or origin.password or origin.query or origin.fragment or origin.path not in {"", "/"}:
        parser.error("--base-url must be an absolute http(s) origin without credentials.")
    if not 0 < args.timeout <= 120:
        parser.error("--timeout must be greater than 0 and at most 120.")
    checks = [
        ("GET", "/health"),
        ("GET", "/api/system/status"),
    ]
    if args.probe_providers:
        checks.extend(("POST", path) for path in (
            "/api/system/test-qdrant", "/api/system/test-embedding", "/api/system/test-llm",
        ))
    failed = False
    probes_ran = False
    for method, path in checks:
        try:
            probes_ran = probes_ran or method == "POST"
            status, data = call(method, path, base_url=args.base_url.rstrip("/"), timeout=args.timeout)
            print(f"{method} {path} -> {status}")
            if not 200 <= status < 300:
                raise ValueError(f"http_failure:{status}")
            validate_reply(path, data)
        except (json.JSONDecodeError, UnicodeError):
            print(f"service_check=failed path={path} reason=invalid_json")
            failed = True
            break
        except (URLError, OSError, ValueError) as exc:
            reason = str(exc) if isinstance(exc, ValueError) else "connection_failure"
            print(f"service_check=failed path={path} reason={reason}")
            failed = True
            break
    print(f"real_services_status={'failed' if failed else 'passed'} "
          f"mode={'provider_probe' if args.probe_providers else 'preflight'} "
          f"provider_probes={'not_run' if not probes_ran else 'failed' if failed else 'passed'} "
          f"real_provider_success={'verified' if probes_ran and not failed else 'not_claimed'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
