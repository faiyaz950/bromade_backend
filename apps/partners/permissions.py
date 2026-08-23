from rest_framework.permissions import BasePermission


class IsPartner(BasePermission):
    message = 'Partner profile required.'

    def has_permission(self, request, view):
        profile = getattr(request.user, 'partner_profile', None)
        if profile is None or not profile.is_active:
            return False
        return profile.approval_status == profile.ApprovalStatus.APPROVED
