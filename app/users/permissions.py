from rest_framework.permissions import BasePermission


class IsAdminOrDeveloper(BasePermission):
    """Allow access to staff users or users whose profile_type is admin/developer."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_staff or user.is_superuser:
            return True
        return getattr(user, "profile_type", None) in ("admin", "developer")
