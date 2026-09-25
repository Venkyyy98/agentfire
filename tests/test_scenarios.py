from scenarios import INCIDENT_1, INCIDENT_2


def test_two_required_scenarios_are_defined_with_distinct_hidden_truth():
    assert INCIDENT_1.starts_at == "03:14"
    assert INCIDENT_2.starts_at == "18:42"
    assert INCIDENT_1.hidden_root_cause != INCIDENT_2.hidden_root_cause
