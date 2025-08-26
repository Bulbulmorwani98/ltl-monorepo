from rest_framework import permissions
from rest_framework.permissions import BasePermission
from rest_framework.exceptions import NotAuthenticated, PermissionDenied

class IsSuperuser(permissions.BasePermission):
    """
    Allows access only to superusers.
    """

    def has_permission(self, request, view):
        current_role = int(request.headers.get("Role", None))
        if current_role != 0:
            return False
        # Check if the user's role matches the current role
        if request.user.role != current_role:
            return False
        return request.user and request.user.is_superuser


class IsOrganizationadmin(permissions.BasePermission):
    """
    Allows access only to organization admins.
    """

    def has_permission(self, request, view):
        user = getattr(request, "user", None)

        if not user or not user.is_authenticated:
            raise NotAuthenticated("Authentication credentials were not provided.")

        current_role = request.headers.get("Role")
        if not current_role or int(current_role) != 1:
            return False

        if int(request.user.role) != int(current_role):
            return False

        return True



class IsSuperAdminHost(BasePermission):
    def has_permission(self, request, view):
        return getattr(request, "is_superadmin", False)


class IscreatororManager(permissions.BasePermission):
    """
    Allows access only to Creator or Manager.
    """

    def has_permission(self, request, view):
        current_role = int(request.headers.get("Role", None))
        if current_role == 3 or current_role == 4:
            return request.user
        # Check if the user's role matches the current role
        if request.user.role != current_role:
            return False
        return request.user