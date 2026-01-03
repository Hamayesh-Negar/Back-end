from functools import wraps
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from .models import Conference, ConferenceMember


class ConferencePermissionMixin:

    conference_lookup_field = 'conference_id'
    permission_required = None

    def get_conference(self):
        conference_id = self.kwargs.get(self.conference_lookup_field)
        conference_slug = self.kwargs.get('conference_slug')
        conference_pk = self.kwargs.get('conference_pk')

        if conference_slug:
            return get_object_or_404(Conference, slug=conference_slug)
        elif conference_pk:
            return get_object_or_404(Conference, pk=conference_pk)
        elif conference_id:
            return get_object_or_404(Conference, pk=conference_id)
        else:
            obj = getattr(self, 'object', None)
            if obj and hasattr(obj, 'conference'):
                return obj.conference
            elif obj and isinstance(obj, Conference):
                return obj
            else:
                raise ValueError(
                    "Unable to determine conference for permission checking")

    def get_user_membership(self, conference=None):
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
        if not self.request.user.is_authenticated:
            return "Authentication required."

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

    def check_permissions(self, request):
        super().check_permissions(request)

        if not request.user.is_authenticated:
            raise PermissionDenied("Authentication required.")

        if request.user.is_superuser:
            return

        conference = self.get_conference()

        status_message = self.check_member_status(conference)
        if status_message:
            raise PermissionDenied(status_message)

        membership = self.get_user_membership(conference)

        if not membership or membership.role.role_type != 'secretary':
            raise PermissionDenied(
                "Only conference secretary can access this resource.")


class ConferenceExecutiveRequiredMixin(ConferencePermissionMixin):

    def check_permissions(self, request):
        super().check_permissions(request)

        if not request.user.is_authenticated:
            raise PermissionDenied("Authentication required.")

        if request.user.is_superuser:
            return

        conference = self.get_conference()

        status_message = self.check_member_status(conference)
        if status_message:
            raise PermissionDenied(status_message)

        membership = self.get_user_membership(conference)

        if not membership or membership.role.role_type not in ['secretary', 'deputy', 'assistant']:
            raise PermissionDenied(
                "Only conference executives can access this resource.")


class ConferenceMemberRequiredMixin(ConferencePermissionMixin):

    def check_permissions(self, request):
        super().check_permissions(request)

        if not request.user.is_authenticated:
            raise PermissionDenied("Authentication required.")

        if request.user.is_superuser:
            return

        conference = self.get_conference()

        status_message = self.check_member_status(conference)
        if status_message:
            raise PermissionDenied(status_message)

        membership = self.get_user_membership(conference)

        if not membership:
            raise PermissionDenied(
                "Only conference members can access this resource.")


def conference_permission_required(permission_codename, conference_lookup='conference_id'):
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
