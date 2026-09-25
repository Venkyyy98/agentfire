"""Lightweight production simulator. Tool methods expose observations, never hidden truth."""
from __future__ import annotations

from copy import deepcopy

from scenarios import Scenario


class ProductionSimulator:
    def __init__(self) -> None:
        self.services = {
            "payment": {"status": "healthy", "latency": 120, "error_rate": 0.01},
            "checkout": {"status": "healthy", "latency": 110, "error_rate": 0.01},
            "auth": {"status": "healthy", "token_valid": True},
            "database": {"status": "healthy", "connections": 34, "max_connections": 100, "latency": 22},
            "queue": {"status": "healthy", "depth": 17},
        }
        self._scenario: Scenario | None = None

    def inject(self, scenario: Scenario) -> None:
        self._scenario = scenario
        if scenario.hidden_root_cause == "expired_shared_auth_credential":
            self.services["auth"].update(status="degraded", token_valid=False)
            for service in ("payment", "checkout"):
                self.services[service].update(status="degraded", error_rate=0.72, latency=820)
        elif scenario.hidden_root_cause == "database_connection_exhaustion":
            self.services["database"].update(status="degraded", connections=100, latency=950)
            for service in ("payment", "checkout"):
                self.services[service].update(status="degraded", error_rate=0.68, latency=900)

    def public_statuses(self) -> dict[str, str]:
        return {name: values["status"] for name, values in self.services.items()}

    def get_metrics(self, service: str) -> dict:
        self._check_service(service)
        return deepcopy(self.services[service])

    def get_logs(self, service: str) -> list[str]:
        self._check_service(service)
        if self._scenario and self._scenario.hidden_root_cause == "expired_shared_auth_credential":
            if service == "auth":
                return ["TOKEN_EXPIRED: shared credential rejected by upstream authentication provider"]
            if service in {"payment", "checkout"}:
                return ["HTTP 401: upstream authentication failure"]
        if self._scenario and self._scenario.hidden_root_cause == "database_connection_exhaustion":
            if service == "auth":
                return ["Auth token validation normal; no authentication failures observed"]
            if service in {"payment", "checkout"}:
                return ["Request timeout while acquiring downstream persistence connection"]
            if service == "database":
                return ["Connection pool exhausted: 100/100 active connections"]
        return [f"{service} operating normally"]

    def get_dependencies(self, service: str) -> list[str]:
        self._check_service(service)
        return {"payment": ["auth", "database", "queue"], "checkout": ["auth", "database", "queue"]}.get(service, [])

    def restart_service(self, service: str) -> dict:
        self._check_service(service)
        return {"service": service, "result": "restarted", "recovered": False}

    def refresh_credentials(self, service: str) -> dict:
        if service != "auth":
            return {"service": service, "result": "unsupported", "recovered": False}
        if self._scenario and self._scenario.hidden_root_cause == "expired_shared_auth_credential":
            self.services["auth"].update(status="healthy", token_valid=True)
            for dependent in ("payment", "checkout"):
                self.services[dependent].update(status="healthy", error_rate=0.01, latency=120)
            return {"service": service, "result": "credentials_refreshed", "recovered": True}
        return {"service": service, "result": "credentials_valid_no_change", "recovered": False}

    def recover_database_pool(self) -> dict:
        if self._scenario and self._scenario.hidden_root_cause == "database_connection_exhaustion":
            self.services["database"].update(status="healthy", connections=34, latency=22)
            for dependent in ("payment", "checkout"):
                self.services[dependent].update(status="healthy", error_rate=0.01, latency=120)
            return {"result": "pool_recovered", "recovered": True}
        return {"result": "no_pool_problem_detected", "recovered": False}

    def verify_service(self, service: str) -> dict:
        self._check_service(service)
        data = self.services[service]
        return {"service": service, "healthy": data["status"] == "healthy", "status": data["status"]}

    def incident_recovered(self) -> bool:
        return self.services["payment"]["status"] == "healthy" and self.services["checkout"]["status"] == "healthy"

    def _check_service(self, service: str) -> None:
        if service not in self.services:
            raise ValueError(f"Unknown simulated service: {service}")
