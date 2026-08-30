from rest_framework.permissions import BasePermission


class IsPartnerAccount(BasePermission):
    message = 'Partner profile required.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, 'partner_profile', None))


class IsApprovedPartner(BasePermission):
    message = 'Approved partner profile required.'

    def has_permission(self, request, view):
        profile = getattr(request.user, 'partner_profile', None)
        if profile is None or not profile.is_active:
            return False
        return profile.approval_status == profile.ApprovalStatus.APPROVED


# Back-compat alias used by existing job endpoints.
IsPartner = IsApprovedPartner
