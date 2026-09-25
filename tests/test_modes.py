import pytest

from shift import EnduranceShift


def test_explicit_fallback_mode_still_passes():
    run = EnduranceShift(agent_mode="fallback").run_incident_1()
    assert run["evaluation"]["pass"] is True


def test_llm_mode_does_not_silently_fallback_without_credentials(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="requires OPENAI_API_KEY"):
        EnduranceShift(agent_mode="llm").run_incident_1()
