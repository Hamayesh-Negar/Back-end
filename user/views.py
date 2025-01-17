from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from user.models import User
from user.permissions import IsSuperuser
from user.serializers import UserSerializer, UserBaseSerializer, UserCreateSerializer, UserChangePasswordSerializer


class UserViewSet(ModelViewSet):
    queryset = User.objects.all()
    permission_classes = [IsAuthenticated, IsSuperuser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'user_type']
    search_fields = ['first_name', 'last_name', 'email', 'phone']
    ordering_fields = ['first_name', 'last_name', 'date_joined']
    ordering = ['-date_joined']

    def get_queryset(self):
        user = self.request.user
        queryset = User.objects.all()

        if not isinstance(user, User):
            return queryset.none()

        if user.is_superuser:
            return queryset
        elif user.user_type == User.UserType.HAMAYESH_MANAGER:
            return queryset.filter(user_type=User.UserType.HAMAYESH_YAR)
        return queryset.filter(id=user.id)

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return UserBaseSerializer
        elif self.action == 'change_password':
            return UserChangePasswordSerializer
        return UserSerializer

    @action(detail=True, methods=['post'])
    def change_password(self, request, pk=None):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {'status': 'Password changed successfully'}
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        user = self.get_object()
        user.is_active = True
        user.save()
        serializer = self.get_serializer(user)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        user = self.get_object()
        user.is_active = False
        user.save()
        serializer = self.get_serializer(user)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def make_manager(self, request, pk=None):
        user = self.get_object()
        user.user_type = User.UserType.HAMAYESH_MANAGER
        user.save()
        serializer = self.get_serializer(user)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def make_yar(self, request, pk=None):
        user = self.get_object()
        user.user_type = User.UserType.HAMAYESH_YAR
        user.save()
        serializer = self.get_serializer(user)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[IsSuperuser])
    def statistics(self, request):
        queryset = self.queryset
        stat = {
            'total_users': queryset.count(),
            'hamayesh_managers': queryset.filter(user_type=User.UserType.HAMAYESH_MANAGER).count(),
            'hamayesh_yars': queryset.filter(user_type=User.UserType.HAMAYESH_YAR).count(),
            'active_users': queryset.filter(is_active=True).count(),
            'inactive_users': queryset.filter(is_active=False).count(),
        }
        return Response(stat)

    def destroy(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return Response({'detail': 'You do not have permission to perform this action.'},
                            status=403)
        return super().destroy(request, *args, **kwargs)
