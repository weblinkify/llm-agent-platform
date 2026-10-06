INCIDENTS = {
    "INC-1003": {
        "incident_id": "INC-1003",
        "title": "5G service degradation",
        "status": "ACTIVE",
        "severity": "P1",
        "location": "Helsinki",
        "description": "Network degradation affecting 5G customers.",
    }
}


def get_incident(incident_id: str) -> dict:
    incident = INCIDENTS.get(incident_id)

    if not incident:
        return {
            "found": False,
            "incident_id": incident_id,
        }

    return {
        "found": True,
        **incident,
    }


def search_incidents(
    location: str | None = None,
    status: str | None = None,
) -> list[dict]:
    results = []

    for incident in INCIDENTS.values():
        if location and incident["location"].lower() != location.lower():
            continue

        if status and incident["status"].lower() != status.lower():
            continue

        results.append(incident)

    return results


def get_network_status(location: str) -> dict:
    incidents = search_incidents(
        location=location,
        status="ACTIVE",
    )

    return {
        "location": location,
        "status": "DEGRADED" if incidents else "NORMAL",
        "active_incidents": incidents,
    }
