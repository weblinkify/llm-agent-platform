from datetime import UTC, datetime

INCIDENT_STORE: dict[str, dict] = {}


def create_incident(
    title: str,
    description: str,
    severity: str,
) -> dict:

    incident_id = f"INC-{1000 + len(INCIDENT_STORE) + 1}"

    incident = {
        "incident_id": incident_id,
        "title": title,
        "description": description,
        "severity": severity,
        "status": "OPEN",
        "created_at": datetime.now(UTC).isoformat(),
    }

    INCIDENT_STORE[incident_id] = incident

    return incident


def notify_support_team(
    message: str,
) -> dict:

    return {
        "success": True,
        "message": message,
        "notification_status": "SENT",
    }
