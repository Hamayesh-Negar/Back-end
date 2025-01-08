from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from person.models import Person, Category, PersonTask
from person.serializers import PersonSerializer, CategorySerializer
from user.permissions import IsHamayeshManager, IsSuperuser


class PersonViewSet(ModelViewSet):
    queryset = Person.objects.all()
    serializer_class = PersonSerializer
    permission_classes = [IsAuthenticated, IsHamayeshManager, IsSuperuser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filtetset_fields = ['is_active']
    search_fields = ['first_name', 'last_name', 'telephone', 'email']
    ordering_fields = ['created_at']

    def get_queryset(self):
        queryset = super().get_queryset()
        conference_id = self.request.query_params.get('conference_id', None)
        if conference_id:
            queryset = queryset.filter(conference_id=conference_id)
        return queryset

    @action(detail=True, methods=['get'])
    def tasks_summary(self, request, pk=None):
        person = self.get_object()
        tasks = person.tasks.select_related('task').all()
        summary = {
            'total': tasks.count(),
            'completed': tasks.filter(status=PersonTask.COMPLETED).count(),
            'pending': tasks.filter(status=PersonTask.PENDING).count(),
            'in_progress': tasks.filter(status=PersonTask.IN_PROGRESS).count(),
        }
        return Response(summary)


class CategoryViewSet(ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated, IsHamayeshManager, IsSuperuser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filtetset_fields = ['is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['members_count']

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.members.exists():
            return Response(
                {"detail": "Cannot delete category with existing members"},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)
