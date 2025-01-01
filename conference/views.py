from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from conference.models import Conference
from conference.serializers import ConferenceSerializer
from user.permissions import IsHamayeshManager, IsSuperuser


class ConferenceViewSet(ModelViewSet):
    queryset = Conference.objects.all()
    serializer_class = ConferenceSerializer
    permission_classes = [IsAuthenticated, IsSuperuser, IsHamayeshManager]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filtetset_fields = ['is_active']
    search_fields = ['name', 'created_by__first_name', 'created_by__last_name']
    ordering_fields = ['start_date', 'end_date']

    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        conference = self.get_object()
        sets = {
            'total_attendees': conference.attendees.count(),
            'total_tasks': conference.tasks.count(),
            'total_categories': conference.categories.count(),
        }
        return Response(sets)
