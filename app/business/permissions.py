"""Ownership-based permissions for Business and Collaborator viewsets."""

from rest_framework.permissions import BasePermission, SAFE_METHODS

from .models import Collaborator

OWNER_ADMIN_ROLES = ("owner", "admin")


def is_business_collaborator(user, business_id) -> bool:
    if not user or not user.is_authenticated:
        return False
    return Collaborator.objects.filter(
        user=user,
        business_id=business_id,
        is_active=True,
        is_deleted=False,
    ).exists()


def is_business_owner_or_admin(user, business_id) -> bool:
    if not user or not user.is_authenticated:
        return False
    return Collaborator.objects.filter(
        user=user,
        business_id=business_id,
        is_active=True,
        is_deleted=False,
        role__name__in=OWNER_ADMIN_ROLES,
    ).exists()


class IsBusinessCollaboratorOrAdminWrite(BasePermission):
    """
    Read access for any active collaborator of the business.
    Write access (PATCH/DELETE) only for owner/admin or staff.
    Create handled at view level (any authenticated user can create their own business).
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        if request.method in SAFE_METHODS:
            return is_business_collaborator(request.user, obj.id)
        return is_business_owner_or_admin(request.user, obj.id)


class CanManageCollaborators(BasePermission):
    """
    Mutating collaborators of a business requires the requester to be
    owner/admin of that business (or staff).
    Reading is allowed for any active collaborator of the same business.
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.is_staff:
            return True

        # For create, the target business comes from the request body.
        if view.action == "create":
            business_id = request.data.get("business")
            if not business_id:
                return False
            return is_business_owner_or_admin(request.user, business_id)

        # List/retrieve handled at queryset level; let it through here.
        return True

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        if request.method in SAFE_METHODS:
            return is_business_collaborator(request.user, obj.business_id)
        # Allow a user to remove themselves from a business.
        if request.method == "DELETE" and obj.user_id == request.user.id:
            return True
        return is_business_owner_or_admin(request.user, obj.business_id)
