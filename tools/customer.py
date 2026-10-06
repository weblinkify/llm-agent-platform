CUSTOMERS = {
    "10001": {
        "customer_id": "10001",
        "name": "Demo Customer",
        "status": "ACTIVE",
        "services": [
            "Broadband",
        ],
        "eligible_products": [
            "5G Mobile"
        ],
    },
    "10002": {
        "customer_id": "10002",
        "name": "Demo Customer 2",
        "status": "ACTIVE",
        "services": [
            "Broadband",
            "5G Mobile",
        ],
    },
}


def get_customer(customer_id: str) -> dict:
    customer = CUSTOMERS.get(customer_id)

    if not customer:
        return {
            "found": False,
            "customer_id": customer_id,
        }

    return {
        "found": True,
        **customer,
    }


def get_customer_services(customer_id: str) -> dict:
    customer = CUSTOMERS.get(customer_id)

    if not customer:
        return {
            "found": False,
            "services": [],
        }

    return {
        "found": True,
        "customer_id": customer_id,
        "services": customer["services"],
    }