"""Role based access resolution (docs/08): roles resolve to department allowlists."""

from __future__ import annotations

from dataclasses import dataclass

# None means unrestricted access. Restricted roles are used by the permission
# evaluation categories in docs/09.
DEFAULT_ROLES: dict[str, list[str] | None] = {
    "analyst": None,
    "reviewer": None,
    "engineer": ["engineering"],
    "external": ["general"],
}


@dataclass(frozen=True)
class Role:
    """A resolved role with its department allowlist."""

    name: str
    departments: frozenset[str] | None  # None means unrestricted


def resolve_role(
    name: str, roles: dict[str, list[str] | None] | None = None
) -> Role:
    """Resolve a role name against the role table; unknown names are hard errors."""
    table = roles if roles is not None else DEFAULT_ROLES
    if name not in table:
        raise KeyError(f"unknown role '{name}'")
    allowlist = table[name]
    return Role(name=name, departments=frozenset(allowlist) if allowlist else None)


def allows(role: Role, departments: set[str] | list[str]) -> bool:
    """Whether the role may see a document carrying these departments."""
    if role.departments is None:
        return True
    return bool(role.departments & set(departments))
