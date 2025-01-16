from rest_framework import filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from user.models import User
from user.permissions import IsSuperuser
from user.serializers import UserSerializer, UserBaseSerializer, UserCreateSerializer


class UserViewSet(ModelViewSet):
    queryset = User.objects.all()
    permission_classes = [IsAuthenticated, IsSuperuser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
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
        else:
            return queryset.filter(id=user.id)

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return UserBaseSerializer
        return UserSerializer

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
