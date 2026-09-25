from shift import EnduranceShift


def test_incident_one_end_to_end_is_autonomous_and_objectively_verified():
    shift = EnduranceShift()
    run = shift.run_incident_1()
    assert run["evaluation"]["pass"] is True
    assert run["evaluation"]["verification_performed"] is True
    assert run["trace"] == [
        "get_metrics:payment", "get_logs:payment", "get_dependencies:payment",
        "get_metrics:auth", "get_logs:auth", "refresh_credentials:auth",
        "verify_service:payment", "verify_service:checkout",
    ]
    assert len(shift.events.events) > 20
    assert shift.scenario_2_defined is True
