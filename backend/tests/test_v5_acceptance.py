from __future__ import annotations

import json
from pathlib import Path

from scripts.check_v5_acceptance import validate_acceptance


ROOT = Path(__file__).resolve().parents[2]


def test_v5_acceptance_validates_report_provenance_and_rejects_tampering(tmp_path) -> None:
    report_path = ROOT / "docs" / "v5_agentic_rag" / "evaluation_report.json"
    dataset_path = ROOT / "evaluation" / "v5" / "cases.jsonl"

    valid = validate_acceptance(report_path, dataset_path=dataset_path, root=ROOT)

    assert valid["status"] == "passed"
    assert valid["checks"]["evaluation_hard_gates"] is True
    assert valid["checks"]["required_implementation_files"] is True
    assert valid["checks"]["cost_measurement_honest"] is True
    assert valid["checks"]["agent_search_pipeline"] is True
    assert valid["checks"]["agent_search_executed"] is True
    assert valid["checks"]["evaluator_digest_matches"] is True

    tampered = json.loads(report_path.read_text(encoding="utf-8"))
    tampered["dataset"]["sha256"] = "0" * 64
    tampered_path = tmp_path / "tampered.json"
    tampered_path.write_text(json.dumps(tampered), encoding="utf-8")

    invalid = validate_acceptance(tampered_path, dataset_path=dataset_path, root=ROOT)

    assert invalid["status"] == "failed"
    assert invalid["checks"]["dataset_digest_matches"] is False

    tampered_search = json.loads(report_path.read_text(encoding="utf-8"))
    tampered_search["provenance"]["agent_search"] = "SqlEvidenceIndex sparse-only"
    tampered_search_path = tmp_path / "tampered-search.json"
    tampered_search_path.write_text(json.dumps(tampered_search), encoding="utf-8")

    invalid_search = validate_acceptance(
        tampered_search_path,
        dataset_path=dataset_path,
        root=ROOT,
    )

    assert invalid_search["status"] == "failed"
    assert invalid_search["checks"]["agent_search_pipeline"] is False
