from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from conference.models import Conference
from conference.serializers import ConferenceSerializer
from person.serializers import CategorySerializer
from user.permissions import CanEditAllFields, CanEditBasicFields


class ConferenceViewSet(ModelViewSet):
    queryset = Conference.objects.all()
    serializer_class = ConferenceSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filtetset_fields = ['is_active']
    search_fields = ['name', 'created_by__first_name', 'created_by__last_name']
    ordering_fields = ['start_date', 'end_date']
    lookup_field = 'slug'
    lookup_value_regex = '[0-9]+|[a-zA-Z0-9-]+'

    def get_object(self):
        """
        Get object by either slug or pk
        """
        queryset = self.get_queryset()
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        lookup_value = self.kwargs[lookup_url_kwarg]

        try:
            lookup_value = int(lookup_value)
            obj = get_object_or_404(queryset, pk=lookup_value)
        except ValueError:
            obj = get_object_or_404(queryset, slug=lookup_value)

        self.check_object_permissions(self.request, obj)
        return obj

    @action(detail=False, methods=['get'])
    def active(self, request):
        queryset = self.get_queryset().filter(is_active=True)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def categories(self, request, slug=None):
        conference = self.get_object()
        categories = conference.categories
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data)

    def get_permissions(self):
        if self.request.user.has_perm('conference.edit_all_fields'):
            permission_classes = [IsAuthenticated, CanEditAllFields]
        else:
            permission_classes = [IsAuthenticated, CanEditBasicFields]
        return [permission() for permission in permission_classes]

    @action(detail=True, methods=['get'])
    def statistics(self, request, slug=None):
        conference = self.get_object()
        sets = {
            'total_attendees': conference.attendees.count(),
            'total_tasks': conference.tasks.count(),
            'total_categories': conference.categories.count(),
        }
        return Response(sets)

    def create(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return Response({'detail': 'You do not have permission to perform this action.'},
                            status=403)
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if not request.user.is_superuser or request.user.is_hamayesh_manager:
            return Response({'detail': 'You do not have permission to perform this action.'},
                            status=403)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return Response({'detail': 'You do not have permission to perform this action.'},
                            status=403)
        return super().destroy(request, *args, **kwargs)
