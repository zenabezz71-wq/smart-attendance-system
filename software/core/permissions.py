from rest_framework.permissions import BasePermission, SAFE_METHODS

from .models import User

R = User.Role


class RolePermission(BasePermission):
    """View declares read_roles / write_roles (sets of role codes)."""

    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated):
            return False
        if u.is_superuser:
            return True
        roles = view.read_roles if request.method in SAFE_METHODS else view.write_roles
        return u.role in roles
