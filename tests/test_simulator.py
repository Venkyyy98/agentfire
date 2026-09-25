from scenarios import INCIDENT_1
from simulator import ProductionSimulator


def test_auth_credential_refresh_recovers_downstream_services():
    simulator = ProductionSimulator()
    simulator.inject(INCIDENT_1)
    assert simulator.get_metrics("auth")["token_valid"] is False
    assert simulator.refresh_credentials("auth")["recovered"] is True
    assert simulator.verify_service("payment")["healthy"] is True
    assert simulator.verify_service("checkout")["healthy"] is True
