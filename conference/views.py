from typing import Union, cast
import logging

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

from conference.models import (
    Conference, ConferenceRole, ConferenceMember, ConferenceInvitation,
    ConferencePermission, InvitationPermission, UserFCMDevice, ConferenceMemberPermission
)
from conference.serializers import (
    ConferenceDetailSerializer, ConferenceSerializer, ConferenceRoleSerializer,
    ConferenceMemberSerializer, ConferenceMemberDetailSerializer, ConferenceInvitationSerializer,
    ConferencePermissionSerializer, ConferenceInvitationWithPermissionsSerializer,
    UserFCMDeviceSerializer, ConferenceMemberPermissionSerializer,
    MemberPermissionUpdateSerializer, MemberPermissionGrantSerializer,
    MemberPermissionRevokeSerializer
)
from conference.permissions import (
    ConferencePermissionMixin, ConferenceSecretaryRequiredMixin,
    ConferenceExecutiveRequiredMixin
)
from conference.fcm_service import fcm_service
from person.serializers import CategorySerializer
from user.permissions import IsSuperuser

logger = logging.getLogger(__name__)


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

        include_conference_permissions = request.query_params.get(
            'conference_permissions', 'false').lower() == 'true'

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
                    'has_direct_permissions': membership.direct_permissions.exists(),
                }

                if include_conference_permissions:
                    # Use combined permissions (role + direct)
                    permissions = list(
                        membership.get_permissions().values_list('codename', flat=True))

                    conference_data['conference_permissions'] = {
                        'can_edit_conference': 'edit_conference' in permissions,
                        'can_delete_conference': 'delete_conference' in permissions,
                        'can_deactivate_conference': 'deactivate_conference' in permissions,
                    }

            except ConferenceMember.DoesNotExist:
                pass
            result.append(conference_data)

        return Response(result, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def user_viewing_permissions(self, request, slug=None):

        conference = self.get_object()
        user = request.user

        if user.is_superuser:
            permissions = ConferencePermission.objects.all().values_list('codename', flat=True)
            return Response({
                'is_superuser': True,
                'permissions': list(permissions),
                'is_member': True,
                'status': 'superuser'
            }, status=status.HTTP_200_OK)

        try:
            membership = ConferenceMember.objects.select_related('role').get(
                user=user,
                conference=conference
            )
        except ConferenceMember.DoesNotExist:
            return Response({
                'error': 'کاربر عضو رویداد نمیباشد.'
            }, status=status.HTTP_200_OK)

        # Use combined permissions (role + direct)
        permissions = list(
            membership.get_permissions().values_list('codename', flat=True))

        return Response({
            'status': membership.status,
            'role': membership.role.name,
            'role_type': membership.role.role_type,
            'has_direct_permissions': membership.direct_permissions.exists(),
            'can_view_tasks': 'view_tasks' in permissions,
            'can_view_categories': 'view_categories' in permissions,
            'can_manage_categories': 'manage_categories' in permissions,
            'can_view_people': 'view_people' in permissions,
            'can_view_members': 'view_members' in permissions,
            'can_view_reports': 'view_reports' in permissions,
            'can_view_registration_forms': 'view_registration_forms' in permissions,
            'can_manage_qr_codes': 'qr_code_management' in permissions,
            'can_scan_qr_codes': 'qr_code_scanning' in permissions,
            'can_add_people': 'add_people' in permissions,
            'can_approve_attendees': 'approve_people' in permissions,
            'can_edit_people_info': 'edit_people_info' in permissions,
            'can_change_people_status': 'change_status_people' in permissions,
            'can_delete_people': 'delete_people' in permissions,
        }, status=status.HTTP_200_OK)

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
            membership = ConferenceMember.objects.select_related('role').prefetch_related(
                'direct_permissions', 'direct_permissions__permission'
            ).get(
                user=request.user,
                conference=conference
            )
            return Response({
                'membership': {
                    'id': membership.id,
                    'role': membership.role.name,
                    'role_type': membership.role.role_type,
                    'status': membership.status,
                    'joined_at': membership.joined_at,
                    'permissions': list(membership.get_permissions().values_list('codename', flat=True)),
                    'role_permissions': list(membership.get_role_permissions().values_list('codename', flat=True)),
                    'direct_granted_permissions': list(membership.get_direct_permissions().values_list('codename', flat=True)),
                    'revoked_permissions': list(membership.get_revoked_permissions().values_list('codename', flat=True)),
                    'has_direct_permissions': membership.direct_permissions.exists(),
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
    serializer_class = ConferenceRoleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        conference_slug = self.kwargs.get('conference_slug')
        if conference_slug:
            return ConferenceRole.objects.filter(conference__slug=conference_slug)
        return ConferenceRole.objects.none()

    def perform_create(self, serializer):
        conference_slug = self.kwargs.get('conference_slug')
        conference = get_object_or_404(Conference, slug=conference_slug)
        serializer.save(conference=conference)


class ConferencePermissionViewSet(ConferenceExecutiveRequiredMixin, ModelViewSet):
    serializer_class = ConferencePermissionSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get']

    def get_queryset(self):
        conference_slug = self.kwargs.get('conference_slug')
        if conference_slug:
            return ConferencePermission.objects.filter(roles__conference__slug=conference_slug).distinct()
        return ConferencePermission.objects.none()


class ConferenceMemberViewSet(ConferenceExecutiveRequiredMixin, ModelViewSet):
    serializer_class = ConferenceMemberSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status', 'role__role_type']
    search_fields = ['user__username', 'user__first_name', 'user__last_name']

    def get_queryset(self):
        conference = self.kwargs.get('conference_slug')
        if conference:
            return ConferenceMember.objects.select_related('user', 'role').prefetch_related(
                'direct_permissions', 'direct_permissions__permission'
            ).filter(conference__slug=conference)
        return ConferenceMember.objects.none()

    def get_serializer_class(self):
        if self.action in ['retrieve', 'permissions', 'permissions_detail']:
            return ConferenceMemberDetailSerializer
        return ConferenceMemberSerializer

    def destroy(self, request, *args, **kwargs):
        member = self.get_object()
        conference = member.conference

        if not self.has_conference_permission('remove_members', conference):
            return Response({'detail': 'You do not have permission to remove members.'},
                            status=status.HTTP_403_FORBIDDEN)

        if member.role.role_type == 'secretary':
            return Response({'detail': 'Cannot remove conference secretary.'},
                            status=status.HTTP_400_BAD_REQUEST)

        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['get'], url_path='permissions-detail')
    def permissions(self, request, pk=None, conference_slug=None):
        member = self.get_object()
        conference = member.conference

        if not self.has_conference_permission('view_members', conference):
            return Response(
                {'detail': 'You do not have permission to view member details.'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = ConferenceMemberDetailSerializer(member)
        return Response(serializer.data)

    @action(detail=True, methods=['put', 'patch'], url_path='permissions-update')
    def update_permissions(self, request, pk=None, conference_slug=None):
        member = self.get_object()
        conference = member.conference

        membership = self.get_user_membership(conference)
        if not membership or membership.role.role_type != 'secretary':
            if not request.user.is_superuser:
                return Response(
                    {'detail': 'Only conference secretary can manage member permissions.'},
                    status=status.HTTP_403_FORBIDDEN
                )

        if member.role.role_type == 'secretary' and member.user != request.user:
            return Response(
                {'detail': 'Cannot modify secretary permissions.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = MemberPermissionUpdateSerializer(data=request.data)
        if serializer.is_valid():
            serializer.update_permissions(member, granted_by=request.user)

            member.refresh_from_db()
            return Response({
                'detail': 'Permissions updated successfully.',
                'member': ConferenceMemberDetailSerializer(member).data
            })

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='permissions-grant')
    def grant_permission(self, request, pk=None, conference_slug=None):
        member = self.get_object()
        conference = member.conference

        membership = self.get_user_membership(conference)
        if not membership or membership.role.role_type != 'secretary':
            if not request.user.is_superuser:
                return Response(
                    {'detail': 'Only conference secretary can grant permissions.'},
                    status=status.HTTP_403_FORBIDDEN
                )

        serializer = MemberPermissionGrantSerializer(data=request.data)
        if serializer.is_valid():
            permission_id = serializer.validated_data['permission_id']
            reason = serializer.validated_data.get('reason', '')

            permission = ConferencePermission.objects.get(id=permission_id)
            ConferenceMemberPermission.objects.update_or_create(
                member=member,
                permission=permission,
                defaults={
                    'is_revoked': False,
                    'granted_by': request.user,
                    'reason': reason
                }
            )

            return Response({
                'detail': f'Permission "{permission.name}" granted successfully.',
                'effective_permissions': list(member.get_permissions().values_list('codename', flat=True))
            })

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='permissions-revoke')
    def revoke_permission(self, request, pk=None, conference_slug=None):
        member = self.get_object()
        conference = member.conference

        membership = self.get_user_membership(conference)
        if not membership or membership.role.role_type != 'secretary':
            if not request.user.is_superuser:
                return Response(
                    {'detail': 'Only conference secretary can revoke permissions.'},
                    status=status.HTTP_403_FORBIDDEN
                )

        serializer = MemberPermissionRevokeSerializer(data=request.data)
        if serializer.is_valid():
            permission_id = serializer.validated_data['permission_id']
            reason = serializer.validated_data.get('reason', '')

            permission = ConferencePermission.objects.get(id=permission_id)
            ConferenceMemberPermission.objects.update_or_create(
                member=member,
                permission=permission,
                defaults={
                    'is_revoked': True,
                    'granted_by': request.user,
                    'reason': reason
                }
            )

            return Response({
                'detail': f'Permission "{permission.name}" revoked successfully.',
                'effective_permissions': list(member.get_permissions().values_list('codename', flat=True))
            })

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='permissions-reset')
    def reset_permissions(self, request, pk=None, conference_slug=None):
        member = self.get_object()
        conference = member.conference

        membership = self.get_user_membership(conference)
        if not membership or membership.role.role_type != 'secretary':
            if not request.user.is_superuser:
                return Response(
                    {'detail': 'Only conference secretary can reset permissions.'},
                    status=status.HTTP_403_FORBIDDEN
                )

        member.reset_permissions_to_role()

        return Response({
            'detail': 'All direct permissions removed. Member now uses role permissions only.',
            'effective_permissions': list(member.get_permissions().values_list('codename', flat=True))
        })

    @action(detail=True, methods=['delete'], url_path='permissions-remove/(?P<permission_id>[^/.]+)')
    def remove_direct_permission(self, request, pk=None, conference_slug=None, permission_id=None):
        member = self.get_object()
        conference = member.conference

        membership = self.get_user_membership(conference)
        if not membership or membership.role.role_type != 'secretary':
            if not request.user.is_superuser:
                return Response(
                    {'detail': 'Only conference secretary can remove direct permissions.'},
                    status=status.HTTP_403_FORBIDDEN
                )

        try:
            permission = ConferencePermission.objects.get(id=permission_id)
            deleted, _ = member.direct_permissions.filter(
                permission=permission).delete()

            if deleted:
                return Response({
                    'detail': f'Direct permission assignment for "{permission.name}" removed.',
                    'effective_permissions': list(member.get_permissions().values_list('codename', flat=True))
                })
            else:
                return Response(
                    {'detail': 'No direct permission assignment found.'},
                    status=status.HTTP_404_NOT_FOUND
                )
        except ConferencePermission.DoesNotExist:
            return Response(
                {'detail': 'Permission not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['get'], url_path='permissions-direct')
    def list_direct_permissions(self, request, pk=None, conference_slug=None):
        member = self.get_object()
        conference = member.conference

        if not self.has_conference_permission('view_members', conference):
            return Response(
                {'detail': 'You do not have permission to view member details.'},
                status=status.HTTP_403_FORBIDDEN
            )

        direct_perms = member.direct_permissions.select_related(
            'permission', 'granted_by').all()
        serializer = ConferenceMemberPermissionSerializer(
            direct_perms, many=True)

        return Response({
            'member_id': member.id,
            'member_username': member.user.username,
            'direct_permissions': serializer.data,
            'granted_count': direct_perms.filter(is_revoked=False).count(),
            'revoked_count': direct_perms.filter(is_revoked=True).count()
        })


class ConferenceInvitationViewSet(ConferenceExecutiveRequiredMixin, ModelViewSet):
    serializer_class = ConferenceInvitationWithPermissionsSerializer
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
            ).prefetch_related('custom_permissions').filter(conference__slug=conference_slug)
        return ConferenceInvitation.objects.none()

    def perform_create(self, serializer):
        conference_slug = self.kwargs.get('conference_slug')
        conference = get_object_or_404(Conference, slug=conference_slug)

        expires_at = timezone.now() + timezone.timedelta(days=7)

        invitation = serializer.save(
            conference=conference,
            invited_by=self.request.user,
            expires_at=expires_at
        )

        self._send_invitation_notification(invitation)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        conference_slug = self.kwargs.get('conference_slug')
        if conference_slug:
            conference = get_object_or_404(Conference, slug=conference_slug)
            context['conference'] = conference
        return context

    def _send_invitation_notification(self, invitation):
        try:
            tokens = list(
                invitation.invited_user.fcm_devices.filter(
                    is_active=True
                ).values_list('device_token', flat=True)
            )

            if tokens:
                fcm_service.send_invitation_notification(
                    user_tokens=tokens,
                    inviter_name=invitation.invited_by.get_full_name() or invitation.invited_by.username,
                    conference_name=invitation.conference.name,
                    invitation_id=invitation.id
                )
                logger.info(
                    f"Invitation notification sent to {invitation.invited_user.username}"
                )
        except Exception as e:
            logger.error(
                f"Failed to send invitation notification: {str(e)}"
            )

    @action(detail=True, methods=['post', 'get'], permission_classes=[IsAuthenticated])
    def permissions(self, request, pk=None, conference_slug=None):
        invitation = self.get_object()

        conference = invitation.conference
        if not self.has_conference_permission('invite_members', conference):
            return Response(
                {'detail': 'You do not have permission to manage invitation permissions.'},
                status=status.HTTP_403_FORBIDDEN
            )

        if request.method == 'GET':
            permissions = invitation.custom_permissions.all()
            serializer = ConferencePermissionSerializer(
                [p.permission for p in permissions],
                many=True
            )
            return Response({
                'invitation_id': invitation.id,
                'permissions': serializer.data,
                'permission_count': len(serializer.data)
            })

        elif request.method == 'POST':
            permission_ids = request.data.get('permission_ids', [])

            if not isinstance(permission_ids, list):
                return Response(
                    {'detail': 'permission_ids must be a list of integers.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                permissions = ConferencePermission.objects.filter(
                    id__in=permission_ids)
                if len(permissions) != len(permission_ids):
                    return Response(
                        {'detail': 'One or more permission IDs are invalid.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                invitation.custom_permissions.all().delete()
                for permission in permissions:
                    InvitationPermission.objects.create(
                        invitation=invitation,
                        permission=permission
                    )

                self._send_permissions_update_notification(
                    invitation, permissions)

                return Response({
                    'detail': 'Invitation permissions updated successfully.',
                    'permissions': ConferencePermissionSerializer(permissions, many=True).data,
                    'permission_count': len(permissions)
                }, status=status.HTTP_200_OK)

            except Exception as e:
                logger.error(
                    f"Error updating invitation permissions: {str(e)}")
                return Response(
                    {'detail': f'Error updating permissions: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

    def _send_permissions_update_notification(self, invitation, permissions):
        try:
            tokens = list(
                invitation.invited_user.fcm_devices.filter(
                    is_active=True
                ).values_list('device_token', flat=True)
            )

            if tokens:
                permission_names = [p.name for p in permissions]
                fcm_service.send_permission_update_notification(
                    user_tokens=tokens,
                    conference_name=invitation.conference.name,
                    permissions=permission_names
                )
                logger.info(
                    f"Permission update notification sent to {invitation.invited_user.username}"
                )
        except Exception as e:
            logger.error(
                f"Failed to send permission update notification: {str(e)}"
            )

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None, conference_slug=None):
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
    def reject(self, request, pk=None, conference_slug=None):
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
    serializer_class = ConferenceInvitationWithPermissionsSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post']

    def get_queryset(self):
        return ConferenceInvitation.objects.select_related(
            'conference', 'invited_by', 'role'
        ).prefetch_related('custom_permissions').filter(invited_user=self.request.user)

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
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
        invitation = self.get_object()

        if invitation.invited_user != request.user:
            return Response({'detail': 'You can only reject your own invitations.'},
                            status=status.HTTP_403_FORBIDDEN)

        try:
            invitation.reject()
            return Response({'detail': 'Invitation rejected successfully.'})
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class UserFCMDeviceViewSet(ModelViewSet):
    serializer_class = UserFCMDeviceSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'put', 'delete']

    def get_queryset(self):
        return UserFCMDevice.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        device = self.get_object()
        if device.user != self.request.user:
            return Response(
                {'detail': 'You can only update your own devices.'},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        device = self.get_object()
        if device.user != request.user:
            return Response(
                {'detail': 'You can only activate your own devices.'},
                status=status.HTTP_403_FORBIDDEN
            )
        device.is_active = True
        device.save()
        return Response({'detail': 'Device activated.'})

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        device = self.get_object()
        if device.user != request.user:
            return Response(
                {'detail': 'You can only deactivate your own devices.'},
                status=status.HTTP_403_FORBIDDEN
            )
        device.is_active = False
        device.save()
        return Response({'detail': 'Device deactivated.'})

    @action(detail=False, methods=['post'])
    def test_notification(self, request):
        devices = self.get_queryset().filter(is_active=True)

        if not devices.exists():
            return Response(
                {'detail': 'No active devices found.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        tokens = list(devices.values_list('device_token', flat=True))
        result = fcm_service.send_multicast(
            tokens=tokens,
            title='تست نوتیفیکیشن 📬',
            body='اگر این پیام را می‌بینید، FCM به درستی کار می‌کند!'
        )

        return Response({
            'detail': 'Test notification sent.',
            'result': result
        })
