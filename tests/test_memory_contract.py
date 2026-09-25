from memory import DurableExperience


def test_durable_experience_contract_is_phase_three_ready():
    memory = DurableExperience(memory_id="INC-001", incident_id="INC-001",
                               symptoms=["payment degraded"], root_cause="auth dependency",
                               reusable_lesson="401 errors may indicate shared auth",
                               do_not_assume="Verify auth health before action",
                               confidence=0.91, source_run_id="RUN-1")
    memory.validate()
    row = memory.as_dict()
    assert row["source"] == "liquid"
    assert row["symptoms"] == ["payment degraded"]
    assert row["created_at"]
    assert row["source_run_id"] == "RUN-1"


def test_durable_experience_rejects_unsafe_certain_lesson():
    memory = DurableExperience(memory_id="MEM-1", incident_id="INC-001", root_cause="auth",
                               reusable_lesson="Always refresh auth when checkout fails",
                               do_not_assume="Verify auth first", source_run_id="RUN-1")
    try:
        memory.validate()
        assert False, "unsafe certain lesson should fail validation"
    except ValueError as error:
        assert "preserve uncertainty" in str(error)
