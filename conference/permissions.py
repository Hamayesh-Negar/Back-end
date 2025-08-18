from functools import wraps
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from .models import Conference, ConferenceMember


class ConferencePermissionMixin:
    """
    Mixin to handle conference-specific permission checking in views.

    This mixin provides methods to check if the current user has specific
    permissions within a conference context.
    """
    conference_lookup_field = 'conference_id'
    permission_required = None

    def get_conference(self):
        """Get the conference object for permission checking"""
        conference_id = self.kwargs.get(self.conference_lookup_field)
        if not conference_id:
            obj = getattr(self, 'object', None)
            if obj and hasattr(obj, 'conference'):
                return obj.conference
            elif obj and isinstance(obj, Conference):
                return obj
            else:
                raise ValueError(
                    "Unable to determine conference for permission checking")

        return get_object_or_404(Conference, pk=conference_id)

    def get_user_membership(self, conference=None):
        """Get the user's membership in the conference"""
        if not self.request.user.is_authenticated:
            return None

        conference = conference or self.get_conference()

        try:
            return ConferenceMember.objects.select_related('role').get(
                user=self.request.user,
                conference=conference,
                status='active'
            )
        except ConferenceMember.DoesNotExist:
            return None

    def has_conference_permission(self, permission_codename, conference=None):
        """Check if the current user has a specific permission in the conference"""
        if not self.request.user.is_authenticated:
            return False

        if self.request.user.is_superuser:
            return True

        conference = conference or self.get_conference()
        membership = self.get_user_membership(conference)

        if not membership:
            return False

        if membership.status != 'active':
            return False

        return membership.has_permission(permission_codename)

    def check_member_status(self, conference=None):
        """Check member status"""
        if not self.request.user.is_authenticated:
            raise PermissionDenied("Authentication required.")

        if self.request.user.is_superuser:
            return None

        conference = conference or self.get_conference()

        try:
            membership = ConferenceMember.objects.select_related('role').get(
                user=self.request.user,
                conference=conference
            )
        except ConferenceMember.DoesNotExist:
            return "You are not a member of this conference."

        if membership.status == 'suspended':
            return "Membership suspended."
        elif membership.status == 'inactive':
            return "Membership inactive."

        return None  # Member is active

    def check_conference_permission(self, permission_codename=None, conference=None):
        """Check permission and raise PermissionDenied if not allowed"""
        permission = permission_codename or self.permission_required

        if not permission:
            raise ValueError("No permission specified for checking")

        # First check member status
        status_message = self.check_member_status(conference)
        if status_message:
            raise PermissionDenied(status_message)

        if not self.has_conference_permission(permission, conference):
            raise PermissionDenied(
                f"You don't have '{permission}' permission for this conference."
            )

    def dispatch(self, request, *args, **kwargs):
        """Override dispatch to check permissions before processing the request"""
        if self.permission_required:
            self.check_conference_permission()

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """Add conference context data to the template context"""
        context = super().get_context_data(**kwargs)

        try:
            conference = self.get_conference()
            membership = self.get_user_membership(conference)

            context.update({
                'conference': conference,
                'user_membership': membership,
                'user_role': membership.role if membership else None,
                'user_permissions': list(membership.get_permissions().values_list('codename', flat=True)) if membership else [],
            })
        except (ValueError, Conference.DoesNotExist):
            pass

        return context


class ConferenceSecretaryRequiredMixin(ConferencePermissionMixin):
    """Mixin that requires user to be a conference secretary"""

    def dispatch(self, request, *args, **kwargs):
        """Check if user is secretary of the conference"""
        if not request.user.is_authenticated:
            raise PermissionDenied("Authentication required.")

        if request.user.is_superuser:
            return super(ConferencePermissionMixin, self).dispatch(request, *args, **kwargs)

        conference = self.get_conference()

        status_message = self.check_member_status(conference)
        if status_message:
            raise PermissionDenied(status_message)

        membership = self.get_user_membership(conference)

        if not membership or membership.role.role_type != 'secretary':
            raise PermissionDenied(
                "Only conference secretary can access this resource.")

        return super(ConferencePermissionMixin, self).dispatch(request, *args, **kwargs)


class ConferenceExecutiveRequiredMixin(ConferencePermissionMixin):
    """Mixin that requires user to be a conference executive (secretary, deputy, or assistant)"""

    def dispatch(self, request, *args, **kwargs):
        """Check if user is an executive of the conference"""
        if not request.user.is_authenticated:
            raise PermissionDenied("Authentication required.")

        if request.user.is_superuser:
            return super(ConferencePermissionMixin, self).dispatch(request, *args, **kwargs)

        conference = self.get_conference()

        status_message = self.check_member_status(conference)
        if status_message:
            raise PermissionDenied(status_message)

        membership = self.get_user_membership(conference)

        if not membership or membership.role.role_type not in ['secretary', 'deputy', 'assistant']:
            raise PermissionDenied(
                "Only conference executives can access this resource.")

        return super(ConferencePermissionMixin, self).dispatch(request, *args, **kwargs)


class ConferenceMemberRequiredMixin(ConferencePermissionMixin):
    """Mixin that requires user to be a member of the conference"""

    def dispatch(self, request, *args, **kwargs):
        """Check if user is a member of the conference"""
        if not request.user.is_authenticated:
            raise PermissionDenied("Authentication required.")

        if request.user.is_superuser:
            return super(ConferencePermissionMixin, self).dispatch(request, *args, **kwargs)

        conference = self.get_conference()

        status_message = self.check_member_status(conference)
        if status_message:
            raise PermissionDenied(status_message)

        membership = self.get_user_membership(conference)

        if not membership:
            raise PermissionDenied(
                "Only conference members can access this resource.")

        return super(ConferencePermissionMixin, self).dispatch(request, *args, **kwargs)


def conference_permission_required(permission_codename, conference_lookup='conference_id'):
    """
    Decorator for function-based views to check conference permissions.

    Usage:
        @conference_permission_required('edit_conference')
        def my_view(request, conference_id):
            # view logic here
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied("Authentication required.")

            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            conference_id = kwargs.get(conference_lookup)
            if not conference_id:
                raise ValueError(
                    f"Conference ID not found in URL parameters: {conference_lookup}")

            conference = get_object_or_404(Conference, pk=conference_id)

            try:
                membership = ConferenceMember.objects.select_related('role').get(
                    user=request.user,
                    conference=conference
                )

                if membership.status == 'suspended':
                    raise PermissionDenied(
                        "Membership suspended.")
                elif membership.status == 'inactive':
                    raise PermissionDenied(
                        "Membership inactive.")

            except ConferenceMember.DoesNotExist:
                raise PermissionDenied(
                    "You are not a member of this conference.")

            if not request.user.has_conference_permission(conference, permission_codename):
                raise PermissionDenied(
                    f"You don't have '{permission_codename}' permission for this conference."
                )

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator


def conference_secretary_required(conference_lookup='conference_id'):
    """Decorator that requires user to be conference secretary"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied("Authentication required.")

            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            conference_id = kwargs.get(conference_lookup)
            if not conference_id:
                raise ValueError(
                    f"Conference ID not found in URL parameters: {conference_lookup}")

            conference = get_object_or_404(Conference, pk=conference_id)

            try:
                membership = ConferenceMember.objects.select_related('role').get(
                    user=request.user,
                    conference=conference
                )

                if membership.status == 'suspended':
                    raise PermissionDenied(
                        "Membership suspended.")
                elif membership.status == 'inactive':
                    raise PermissionDenied(
                        "Membership inactive.")

                role = membership.role

            except ConferenceMember.DoesNotExist:
                raise PermissionDenied(
                    "You are not a member of this conference.")

            if not role or role.role_type != 'secretary':
                raise PermissionDenied(
                    "Only conference secretary can access this resource.")

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator


def conference_executive_required(conference_lookup='conference_id'):
    """Decorator that requires user to be conference executive"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied("Authentication required.")

            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            conference_id = kwargs.get(conference_lookup)
            if not conference_id:
                raise ValueError(
                    f"Conference ID not found in URL parameters: {conference_lookup}")

            conference = get_object_or_404(Conference, pk=conference_id)

            try:
                membership = ConferenceMember.objects.select_related('role').get(
                    user=request.user,
                    conference=conference
                )

                if membership.status == 'suspended':
                    raise PermissionDenied(
                        "Membership suspended.")
                elif membership.status == 'inactive':
                    raise PermissionDenied(
                        "Membership inactive.")

                role = membership.role

            except ConferenceMember.DoesNotExist:
                raise PermissionDenied(
                    "You are not a member of this conference.")

            if not role or role.role_type not in ['secretary', 'deputy', 'assistant']:
                raise PermissionDenied(
                    "Only conference executives can access this resource.")

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator
