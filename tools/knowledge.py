DOCUMENTS = [
    {
        "id": "DOC-001",
        "title": "Priority Incident SLA",
        "content": (
            "Priority 1 network incidents require immediate operational "
            "attention according to the enterprise incident management policy."
        ),
    },
    {
        "id": "DOC-002",
        "title": "5G Activation Procedure",
        "content": (
            "Customers must have a compatible 5G plan before attempting 5G activation."
        ),
    },
]


def search_knowledge_base(query: str) -> list[dict]:

    query_words = set(query.lower().split())

    results = []

    for document in DOCUMENTS:
        text = (document["title"] + " " + document["content"]).lower()

        score = sum(1 for word in query_words if word in text)

        if score > 0:
            results.append(
                {
                    **document,
                    "score": score,
                }
            )

    results.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return results[:5]
