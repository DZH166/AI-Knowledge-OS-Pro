from tests.test_v4_4_observability import (
    test_v4_4_observability_routes_return_recent_runtime_signals as _observability_contract,
)


def test_observability_routes_contract(db_session, knowledge_space, monkeypatch) -> None:
    _observability_contract(db_session, knowledge_space, monkeypatch)
