from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from user.models import User, UserPreference
from user.permissions import IsSuperuser
from user.serializers import (
    UserSerializer,
    UserChangePasswordSerializer, UserUpdateSerializer, UserPreferenceSerializer
)


class UserViewSet(ModelViewSet):
    queryset = User.objects.all()
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'user_type']
    search_fields = ['username', 'first_name', 'last_name', 'email', 'phone']
    ordering_fields = ['first_name', 'last_name', 'date_joined']
    ordering = ['-date_joined']

    def get_permissions(self):

        if self.action in ['update', 'partial_update']:
            permission_classes = [IsAuthenticated]
        elif self.action == 'destroy':
            permission_classes = [IsAuthenticated, IsSuperuser]
        elif self.action in ['list', 'retrieve']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAuthenticated]

        return [permission() for permission in permission_classes]

    def get_queryset(self):
        user = self.request.user
        queryset = User.objects.all()

        if not isinstance(user, User):
            return queryset.none()

        if user.is_superuser:
            return queryset
        elif user.user_type == User.UserType.HAMAYESH_MANAGER:
            return queryset.filter(
                user_type__in=[User.UserType.HAMAYESH_YAR,
                               User.UserType.NORMAL_USER]
            )
        elif user.user_type == User.UserType.HAMAYESH_YAR:
            return queryset.filter(
                user_type=User.UserType.NORMAL_USER
            ).union(queryset.filter(id=user.id))
        else:
            return queryset.filter(id=user.id)

    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        elif self.action == 'change_password':
            return UserChangePasswordSerializer
        return UserSerializer

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def change_password(self, request, pk=None):
        user = self.get_object()
        if user != request.user and not request.user.is_superuser:
            return Response(
                {'detail': 'You can only change your own password.'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = self.get_serializer(data=request.data, context={
                                         'request': request, 'user': user})
        if serializer.is_valid():
            serializer.save()
            return Response(
                {'status': 'Password changed successfully'}
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def activate(self, request, pk=None):
        user = self.get_object()
        if not (request.user.is_superuser or request.user.is_hamayesh_manager):
            return Response(
                {'detail': 'شما اجازه انجام این عمل را ندارید.'},
                status=status.HTTP_403_FORBIDDEN
            )
        user.is_active = True
        user.save()
        serializer = self.get_serializer(user)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def deactivate(self, request, pk=None):
        user = self.get_object()
        if not (request.user.is_superuser or request.user.is_hamayesh_manager):
            return Response(
                {'detail': 'شما اجازه انجام این عمل را ندارید.'},
                status=status.HTTP_403_FORBIDDEN
            )
        user.is_active = False
        user.save()
        serializer = self.get_serializer(user)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsSuperuser])
    def make_manager(self, request, pk=None):
        user = self.get_object()
        user.user_type = User.UserType.HAMAYESH_MANAGER
        user.is_staff = True
        user.save()
        serializer = self.get_serializer(user)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def make_yar(self, request, pk=None):
        user = self.get_object()
        if not (request.user.is_superuser or request.user.is_hamayesh_manager):
            return Response(
                {'detail': 'شما اجازه انجام این عمل را ندارید.'},
                status=status.HTTP_403_FORBIDDEN
            )
        user.user_type = User.UserType.HAMAYESH_YAR
        user.save()
        serializer = self.get_serializer(user)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def make_normal_user(self, request, pk=None):
        user = self.get_object()
        if not (request.user.is_superuser or request.user.is_hamayesh_manager):
            return Response(
                {'detail': 'شما اجازه انجام این عمل را ندارید.'},
                status=status.HTTP_403_FORBIDDEN
            )
        user.user_type = User.UserType.NORMAL_USER
        user.is_staff = False
        user.save()
        serializer = self.get_serializer(user)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsSuperuser])
    def make_superuser(self, request, pk=None):
        user = self.get_object()
        user.user_type = User.UserType.SUPER_USER
        user.is_staff = True
        user.is_superuser = True
        user.save()
        serializer = self.get_serializer(user)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[IsSuperuser])
    def statistics(self, request):
        queryset = self.queryset
        stat = {
            'total_users': queryset.count(),
            'normal_users': queryset.filter(user_type=User.UserType.NORMAL_USER).count(),
            'hamayesh_yars': queryset.filter(user_type=User.UserType.HAMAYESH_YAR).count(),
            'hamayesh_managers': queryset.filter(user_type=User.UserType.HAMAYESH_MANAGER).count(),
            'super_users': queryset.filter(user_type=User.UserType.SUPER_USER).count(),
            'active_users': queryset.filter(is_active=True).count(),
            'inactive_users': queryset.filter(is_active=False).count(),
        }
        return Response(stat)

    def destroy(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return Response({'detail': 'شما اجازه انجام این عمل را ندارید.'},
                            status=403)
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=['get', 'post', 'patch'], permission_classes=[IsAuthenticated])
    def preference(self, request):
        user = request.user

        preference, _ = UserPreference.objects.get_or_create(user=user)

        if request.method == 'GET':
            serializer = UserPreferenceSerializer(preference)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = UserPreferenceSerializer(
            preference,
            data=request.data,
            partial=True,
            context={'request': request}
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['delete'], permission_classes=[IsAuthenticated])
    def clear_preference(self, request):
        user = request.user

        try:
            preference = UserPreference.objects.get(user=user)
            preference.selected_conference = None
            preference.save()
            return Response({
                'status': True,
                'detail': 'رویداد انتخابی با موفقیت پاک شد.'
            }, status=status.HTTP_200_OK)
        except UserPreference.DoesNotExist:
            return Response({
                'status': True,
                'detail': 'هیچ انتخابی برای پاک کردن وجود ندارد.'
            }, status=status.HTTP_200_OK)
