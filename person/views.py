from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from yaml import serialize

from person.models import Person, Category, PersonTask, Task
from person.pagination import LargeResultsSetPagination, StandardResultsSetPagination
from person.serializers import PersonSerializer, CategorySerializer, TaskSerializer, PersonTaskSerializer
from user.permissions import IsHamayeshManager, IsSuperuser


class PersonViewSet(ModelViewSet):
    queryset = Person.objects.all()
    serializer_class = PersonSerializer
    permission_classes = [IsAuthenticated, IsHamayeshManager, IsSuperuser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filtetset_fields = ['is_active']
    search_fields = ['first_name', 'last_name', 'telephone', 'email']
    ordering_fields = ['created_at']
    pagination_class = LargeResultsSetPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        conference_id = self.request.query_params.get('conference_id', None)
        if conference_id:
            queryset = queryset.filter(conference_id=conference_id)
        return queryset

    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        person = self.get_object()
        person.is_active = not person.is_active
        person.save()
        return Response(self.get_serializer(person).data)

    @action(detail=True, methods=['get'])
    def tasks_summary(self, request, pk=None):
        person = self.get_object()
        tasks = person.tasks.select_related('task').all()
        summary = {
            'total': tasks.count(),
            'completed': tasks.filter(status=PersonTask.COMPLETED).count(),
            'pending': tasks.filter(status=PersonTask.PENDING).count(),
        }
        return Response(summary)

    @action(detail=True, methods=['get'])
    def tasks(self, request, pk=None):
        person = self.get_object()
        tasks = person.tasks.select_related('task').all()
        serializer = PersonTaskSerializer(tasks, many=True)
        return Response(serializer.data)


class CategoryViewSet(ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated, IsHamayeshManager, IsSuperuser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filtetset_fields = ['is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['members_count']
    pagination_class = LargeResultsSetPagination

    @action(detail=True, methods=['post'])
    def bulk_add_members(self, request, pk=None):
        category = self.get_object()
        person_ids = request.data.get('person_ids', [])

        persons = Person.objects.filter(
            id__in=person_ids,
            conference=category.conference
        )

        category.members.add(*persons)
        return Response({'status': 'Members added successfully'})

    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        category = self.get_object()
        members = category.members
        serializer = PersonSerializer(members, many=True)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.members.exists():
            return Response(
                {"detail": "Cannot delete category with existing members"},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)


class TaskViewSet(ModelViewSet):
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated, IsHamayeshManager, IsSuperuser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'due_date', 'created_at']

    def get_queryset(self):
        return Task.objects.filter(
            conference__admins=self.request.user
        ).select_related('conference')

    @action(detail=True, methods=['post'])
    def bulk_assign(self, request, pk=None):

        task = self.get_object()
        person_ids = request.data.get('person_ids', [])

        existing_assignments = set(task.assignments.values_list('person_id', flat=True))
        new_assignments = set(person_ids) - existing_assignments

        bulk_assignments = [
            PersonTask(
                task=task,
                person_id=person_id,
                status=PersonTask.PENDING
            ) for person_id in new_assignments
        ]

        PersonTask.objects.bulk_create(bulk_assignments)
        return Response({'status': 'Task assigned successfully for the selected persons.'})

    @action(detail=True, methods=['get'])
    def completion_stats(self, request, pk=None):
        task = self.get_object()
        total = task.assignments.count()
        completed = task.assignments.filter(status=PersonTask.COMPLETED).count()
        pending = task.assignments.filter(status=PersonTask.PENDING).count()

        return Response({
            'total_assignments': total,
            'completed': completed,
            'pending': pending,
            'completion_rate': round((completed / total * 100), 2) if total > 0 else 0
        })


class PersonTaskViewSet(ModelViewSet):
    serializer_class = PersonTaskSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'person', 'task']
    ordering_fields = ['created_at', 'completed_at']
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        base_queryset = PersonTask.objects.select_related(
            'person', 'task', 'completed_by'
        )
        return base_queryset.filter(person__conference__admins=self.request.user)

    @action(detail=True, methods=['post'])
    def mark_completed(self, request, pk=None):
        person_task = self.get_object()
        if person_task.status == PersonTask.COMPLETED:
            return Response(
                {'error': 'Task is already completed'},
                status=status.HTTP_400_BAD_REQUEST
            )

        person_task.mark_completed(request.user)
        serializer = self.get_serializer(person_task)
        return Response(serializer.data)
