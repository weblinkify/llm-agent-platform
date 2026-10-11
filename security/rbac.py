from core.models import Role

READ_PUBLIC = {
    "search_knowledge_base",
    "get_product",
    "search_products",
    "get_incident",
    "search_incidents",
    "get_network_status",
}
READ_CUSTOMER = {"get_customer", "search_customer", "get_customer_services"}
WRITE = {"create_incident", "update_incident", "create_notification"}

TOOL_PERMISSIONS: dict[Role, frozenset[str]] = {
    Role.ADMIN: frozenset(READ_PUBLIC | READ_CUSTOMER | WRITE),
    Role.SUPPORT_AGENT: frozenset(READ_PUBLIC | READ_CUSTOMER | WRITE),
    Role.AI_ENGINEER: frozenset(READ_PUBLIC),
    Role.READ_ONLY_USER: frozenset(READ_PUBLIC),
}

# Tools that change enterprise systems are never executed without a human decision.
SENSITIVE_TOOLS = frozenset(WRITE)

APPROVER_ROLES = frozenset({Role.ADMIN, Role.SUPPORT_AGENT})
AUDIT_READER_ROLES = frozenset({Role.ADMIN, Role.AI_ENGINEER})


class PermissionDenied(Exception):
    pass


def can_use_tool(role: Role, tool: str) -> bool:
    return tool in TOOL_PERMISSIONS[role]


def require_tool(role: Role, tool: str) -> None:
    if not can_use_tool(role, tool):
        raise PermissionDenied(f"Role {role.value} is not permitted to call {tool}")
