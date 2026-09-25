from evaluator import evaluate
from scenarios import INCIDENT_1
from simulator import ProductionSimulator


def test_remediation_without_verification_does_not_pass():
    simulator = ProductionSimulator()
    simulator.inject(INCIDENT_1)
    simulator.refresh_credentials("auth")
    result = evaluate(INCIDENT_1, simulator, ["refresh_credentials:auth"], event_count=3)
    assert result["recovery_success"] is False
    assert result["verification_performed"] is False
    assert result["pass"] is False
