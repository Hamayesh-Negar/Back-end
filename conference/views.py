from typing import Union, cast

from django.db import models
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from conference.models import Conference, ConferenceRole, ConferenceMember, ConferenceInvitation, ConferencePermission
from conference.serializers import (
    ConferenceDetailSerializer, ConferenceSerializer, ConferenceRoleSerializer, ConferenceMemberSerializer,
    ConferenceInvitationSerializer, ConferencePermissionSerializer
)
from conference.permissions import (
    ConferencePermissionMixin, ConferenceSecretaryRequiredMixin,
    ConferenceExecutiveRequiredMixin
)
from person.serializers import CategorySerializer
from user.permissions import IsSuperuser


class ConferenceViewSet(ConferencePermissionMixin, ModelViewSet):
    filter_backends = [DjangoFilterBackend,
                       filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'created_by__first_name', 'created_by__last_name']
    ordering_fields = ['start_date', 'end_date']
    lookup_field = 'slug'
    lookup_value_regex = '[0-9]+|[a-zA-Z0-9-]+'
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ConferenceDetailSerializer
        return ConferenceSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Conference.objects.all()

        user_conferences = Conference.objects.filter(
            models.Q(created_by=user) |
            models.Q(members__user=user)
        ).distinct()

        return user_conferences

    def get_object(self):
        queryset = self.get_queryset()
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        lookup_value = self.kwargs[lookup_url_kwarg]
        typed_queryset = cast(
            Union[QuerySet[Conference], type[Conference]], queryset)

        try:
            lookup_value = int(lookup_value)
            obj = get_object_or_404(typed_queryset, pk=lookup_value)
        except ValueError:
            obj = get_object_or_404(typed_queryset, slug=lookup_value)

        self.check_object_permissions(self.request, obj)
        return obj

    @action(detail=False, methods=['get'], permission_classes=[IsSuperuser])
    def active_conferences(self, request):
        queryset = self.get_queryset().filter(is_active=True)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_conferences(self, request):
        user = request.user

        conferences = Conference.objects.filter(
            members__user=user,
            members__status='active'
        ).select_related('created_by').prefetch_related('members').distinct()

        serializer = self.get_serializer(conferences, many=True)

        result = []
        for conference_data in serializer.data:
            conference = conferences.get(id=conference_data['id'])
            try:
                membership = conference.members.get(user=user, status='active')
                conference_data['membership'] = {
                    'role': membership.role.name,
                    'role_type': membership.role.role_type,
                    'status': membership.status,
                }
            except ConferenceMember.DoesNotExist:
                pass
            result.append(conference_data)

        return Response(result, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'])
    def categories(self, request, slug=None):
        conference = self.get_object()

        if not conference.enable_categorization:
            return Response({'detail': 'Categorization is not enabled for this conference.'},
                            status=status.HTTP_400_BAD_REQUEST)

        status_message = self.check_member_status(conference)
        if status_message:
            return Response({'detail': status_message}, status=status.HTTP_403_FORBIDDEN)

        if not self.has_conference_permission('view_conference', conference):
            return Response({'detail': 'You do not have permission to view this conference.'},
                            status=status.HTTP_403_FORBIDDEN)

        categories = conference.categories
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def statistics(self, request, slug=None):
        conference = self.get_object()

        status_message = self.check_member_status(conference)
        if status_message:
            return Response({'detail': status_message}, status=status.HTTP_403_FORBIDDEN)

        if not self.has_conference_permission('view_reports', conference):
            return Response({'detail': 'You do not have permission to view reports.'},
                            status=status.HTTP_403_FORBIDDEN)

        stats = {
            'total_attendees': conference.attendees.count(),
            'total_tasks': conference.tasks.count(),
            'total_categories': conference.categories.count(),
            'total_members': conference.members.filter(status='active').count(),
            'total_active_members': conference.members.filter(status='active').count(),
            'total_inactive_members': conference.members.filter(status='inactive').count(),
            'total_suspended_members': conference.members.filter(status='suspended').count(),
            'executives': conference.members.filter(
                role__role_type__in=['secretary', 'deputy', 'assistant'],
                status='active'
            ).count(),
        }
        return Response(stats)

    @action(detail=True, methods=['get'])
    def members(self, request, slug=None):
        conference = self.get_object()

        status_message = self.check_member_status(conference)
        if status_message:
            return Response({'detail': status_message}, status=status.HTTP_403_FORBIDDEN)

        if not self.has_conference_permission('view_conference', conference):
            return Response({'detail': 'You do not have permission to view members.'},
                            status=status.HTTP_403_FORBIDDEN)

        members = conference.members.select_related(
            'user', 'role')
        serializer = ConferenceMemberSerializer(members, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def invite_member(self, request, slug=None):
        conference = self.get_object()

        status_message = self.check_member_status(conference)
        if status_message:
            return Response({'detail': status_message}, status=status.HTTP_403_FORBIDDEN)

        if not self.has_conference_permission('invite_members', conference):
            return Response({'detail': 'You do not have permission to invite members.'},
                            status=status.HTTP_403_FORBIDDEN)

        serializer = ConferenceInvitationSerializer(
            data=request.data, context={'request': request, 'conference': conference})

        if serializer.is_valid():
            invitation = serializer.save(
                conference=conference, invited_by=request.user)
            return Response(ConferenceInvitationSerializer(invitation).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def create(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)

        response = super().create(request, *args, **kwargs)

        if response.status_code == status.HTTP_201_CREATED:
            conference_data = response.data
            conference_id = conference_data.get('id')

            try:
                conference = Conference.objects.get(id=conference_id)

                secretary_role = ConferenceRole.objects.filter(
                    conference=conference,
                    role_type='secretary'
                ).first()

                if secretary_role:
                    ConferenceMember.objects.create(
                        user=request.user,
                        conference=conference,
                        role=secretary_role
                    )

                    conference_data['message'] = f'Conference created successfully. You have been assigned as the Conference Secretary.'
                else:
                    conference_data['warning'] = 'Conference created but there was an issue creating your membership. Please contact support.'

            except Exception as e:
                conference_data[
                    'warning'] = f'Conference created successfully, but there was an issue with membership creation: {str(e)}'

        return response

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def my_membership(self, request, pk=None):
        """Get current user's membership details for this conference"""
        conference = self.get_object()

        try:
            membership = ConferenceMember.objects.get(
                user=request.user,
                conference=conference
            )
            return Response({
                'membership': {
                    'id': membership.id,
                    'role': membership.role.name,
                    'role_type': membership.role.role_type,
                    'status': membership.status,
                    'joined_at': membership.created_at,
                    'permissions': list(membership.role.permissions.values_list('codename', flat=True))
                },
                'message': self.get_membership_status_message(membership)
            })
        except ConferenceMember.DoesNotExist:
            return Response({
                'membership': None,
                'message': 'You are not a member of this conference.'
            })

    def update(self, request, *args, **kwargs):
        conference = self.get_object()

        status_message = self.check_member_status(conference)
        if status_message:
            return Response({'detail': status_message}, status=status.HTTP_403_FORBIDDEN)

        if not self.has_conference_permission('edit_conference', conference):
            return Response({'detail': 'You do not have permission to edit this conference.'},
                            status=status.HTTP_403_FORBIDDEN)

        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        conference = self.get_object()

        status_message = self.check_member_status(conference)
        if status_message:
            return Response({'detail': status_message}, status=status.HTTP_403_FORBIDDEN)

        if not self.has_conference_permission('delete_conference', conference):
            return Response({'detail': 'You do not have permission to delete this conference.'},
                            status=status.HTTP_403_FORBIDDEN)

        return super().destroy(request, *args, **kwargs)


class ConferenceRoleViewSet(ConferenceSecretaryRequiredMixin, ModelViewSet):
    """ViewSet for managing conference roles - Secretary only"""
    serializer_class = ConferenceRoleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        conference = self.kwargs.get('conference_slug')
        if conference:
            return ConferenceRole.objects.filter(conference_id=conference)
        return ConferenceRole.objects.none()

    def perform_create(self, serializer):
        conference_id = self.kwargs.get('conference_id')
        conference = get_object_or_404(Conference, pk=conference_id)
        serializer.save(conference=conference)


class ConferencePermissionViewSet(ConferenceExecutiveRequiredMixin, ModelViewSet):
    """ViewSet for viewing conference permissions"""
    serializer_class = ConferencePermissionSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get']

    def get_queryset(self):
        conference = self.kwargs.get('conference_slug')
        if conference:
            return ConferencePermission.objects.filter(roles__conference=conference)
        return ConferencePermission.objects.none()


class ConferenceMemberViewSet(ConferenceExecutiveRequiredMixin, ModelViewSet):
    """ViewSet for managing conference members"""
    serializer_class = ConferenceMemberSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status', 'role__role_type']
    search_fields = ['user__username', 'user__first_name', 'user__last_name']

    def get_queryset(self):
        conference = self.kwargs.get('conference_slug')
        if conference:
            return ConferenceMember.objects.select_related('user', 'role').filter(
                conference__slug=conference
            )
        return ConferenceMember.objects.none()

    def destroy(self, request, *args, **kwargs):
        """Remove member"""
        member = self.get_object()
        conference = member.conference

        if not self.has_conference_permission('remove_members', conference):
            return Response({'detail': 'You do not have permission to remove members.'},
                            status=status.HTTP_403_FORBIDDEN)

        if member.role.role_type == 'secretary':
            return Response({'detail': 'Cannot remove conference secretary.'},
                            status=status.HTTP_400_BAD_REQUEST)

        return super().destroy(request, *args, **kwargs)


class ConferenceInvitationViewSet(ConferenceExecutiveRequiredMixin, ModelViewSet):
    """ViewSet for managing conference invitations"""
    serializer_class = ConferenceInvitationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status']
    search_fields = ['invited_user__username',
                     'invited_user__first_name', 'invited_user__last_name']

    def get_queryset(self):
        conference_slug = self.kwargs.get('conference_slug')
        if conference_slug:
            return ConferenceInvitation.objects.select_related(
                'invited_user', 'invited_by', 'role', 'conference'
            ).filter(conference__slug=conference_slug)
        return ConferenceInvitation.objects.none()

    def perform_create(self, serializer):
        conference_slug = self.kwargs.get('conference_slug')
        conference = get_object_or_404(Conference, slug=conference_slug)

        expires_at = timezone.now() + timezone.timedelta(days=7)

        serializer.save(
            conference=conference,
            invited_by=self.request.user,
            expires_at=expires_at
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        conference_slug = self.kwargs.get('conference_slug')
        if conference_slug:
            conference = get_object_or_404(Conference, slug=conference_slug)
            context['conference'] = conference
        return context

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None, conference_id=None):
        """Accept an invitation"""
        invitation = self.get_object()

        if invitation.invited_user != request.user:
            return Response({'detail': 'You can only accept your own invitations.'},
                            status=status.HTTP_403_FORBIDDEN)

        try:
            member = invitation.accept()
            return Response({
                'detail': 'Invitation accepted successfully.',
                'membership': ConferenceMemberSerializer(member).data
            })
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None, conference_id=None):
        """Reject an invitation"""
        invitation = self.get_object()

        if invitation.invited_user != request.user:
            return Response({'detail': 'You can only reject your own invitations.'},
                            status=status.HTTP_403_FORBIDDEN)

        try:
            invitation.reject()
            return Response({'detail': 'Invitation rejected successfully.'})
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class UserInvitationViewSet(ModelViewSet):
    """ViewSet for users to view their own invitations"""
    serializer_class = ConferenceInvitationSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post']

    def get_queryset(self):
        return ConferenceInvitation.objects.select_related(
            'conference', 'invited_by', 'role'
        ).filter(invited_user=self.request.user)

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """Accept an invitation"""
        invitation = self.get_object()

        if invitation.invited_user != request.user:
            return Response({'detail': 'You can only accept your own invitations.'},
                            status=status.HTTP_403_FORBIDDEN)

        try:
            member = invitation.accept()
            return Response({
                'detail': 'Invitation accepted successfully.',
                'membership': ConferenceMemberSerializer(member).data
            })
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject an invitation"""
        invitation = self.get_object()

        if invitation.invited_user != request.user:
            return Response({'detail': 'You can only reject your own invitations.'},
                            status=status.HTTP_403_FORBIDDEN)

        try:
            invitation.reject()
            return Response({'detail': 'Invitation rejected successfully.'})
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
