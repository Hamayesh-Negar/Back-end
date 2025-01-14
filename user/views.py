from rest_framework import filters
from rest_framework.viewsets import ModelViewSet

from user.models import User
from user.permissions import IsSuperuser
from user.serializers import UserSerializer


class UserViewSet(ModelViewSet):
    serializer_class = UserSerializer
    permission_classes = [IsSuperuser]
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