from unicodedata import category
from django.utils import timezone

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from person.models import Person, Category, PersonTask, Task
from person.pagination import LargeResultsSetPagination, StandardResultsSetPagination
from person.serializers import PersonSerializer, CategorySerializer, TaskSerializer, PersonTaskSerializer


class PersonViewSet(ModelViewSet):
    serializer_class = PersonSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend,
                       filters.SearchFilter, filters.OrderingFilter]
    filtetset_fields = ['is_active']
    search_fields = ['first_name', 'last_name', 'telephone', 'email']
    ordering_fields = ['created_at']
    pagination_class = LargeResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'preference') and user.preference.selected_conference:
            return Person.objects.filter(conference=user.preference.selected_conference.id)


    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def toggle_active(self, request, pk=None):
        person = self.get_object()
        person.is_active = not person.is_active
        person.save()
        return Response(
            {
                'success': True,
                'message': 'Person status updated successfully',
                'person': self.get_serializer(person).data
            }
        )

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

    @action(detail=False, methods=['post'])
    def validate_unique_code(self, request):
        hashed_unique_code = request.data.get('hashed_unique_code')

        if not hashed_unique_code:
            return Response({'error': 'hashed_unique_code is required'})

        try:
            person = Person.objects.get(hashed_unique_code=hashed_unique_code)
            serializer = self.get_serializer(person)
            return Response(serializer.data)
        except Person.DoesNotExist:
            return Response({'error': 'Person with this hashed unique code does not exist'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'])
    def submit_task(self, request):
        hashed_unique_code = request.data.get('hashed_unique_code')
        task_id = request.data.get('task_id')

        if not hashed_unique_code:
            return Response({
                'error': 'unique_code is required'
            })

        if not task_id:
            return Response({
                'error': 'task_id is required'
            })

        try:
            person = Person.objects.get(hashed_unique_code=hashed_unique_code)
        except Person.DoesNotExist:
            return Response({
                'error': 'Person with this unique code does not exist'})

        if not person.is_active:
            return Response({
                'error': 'Person is not active, Please contact the conference manager'
            })

        try:
            task = Task.objects.get(id=task_id)
        except Task.DoesNotExist:
            return Response({
                'error': 'Task with this ID does not exist'})

        try:
            person_task = PersonTask.objects.get(person=person, task=task)
        except PersonTask.DoesNotExist:
            return Response({
                'error': 'This task is not assigned to this person'})

        if person_task.status == PersonTask.COMPLETED:
            return Response({
                'error': 'This task has already been completed',
                'person_task': PersonTaskSerializer(person_task).data})

        person_task.status = PersonTask.COMPLETED
        person_task.completed_at = timezone.now()

        if request.user and request.user.is_authenticated:
            person_task.completed_by = request.user

        person_task.save()

        return Response({
            'success': True,
            'message': f'Task "{task.name}" has been successfully completed for {person.get_full_name()}',
            'person_task': PersonTaskSerializer(person_task).data
        })


class CategoryViewSet(ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend,
                       filters.SearchFilter, filters.OrderingFilter]
    filtetset_fields = ['is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['members_count']
    pagination_class = LargeResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'preference') and user.preference.selected_conference:
            return Category.objects.filter(conference=user.preference.selected_conference.id)

    @action(detail=True, methods=['post'])
    def bulk_add_members(self, request, pk=None):
        category = self.get_object()
        person_ids = request.data.get('person_ids', [])

        persons = Person.objects.filter(
            id__in=person_ids,
            conference=category.conference
        )

        category.members.add(*persons)
        return Response({
            'success': True,
            'message': 'Members added successfully',
            'category': self.get_serializer(category).data
        })

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
                {
                    'success': False,
                    'message': 'Cannot delete category with existing members'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)


class TaskViewSet(ModelViewSet):
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend,
                       filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'due_date', 'created_at']

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'preference') and user.preference.selected_conference:
            return Task.objects.filter(conference=user.preference.selected_conference.id)

    @action(detail=True, methods=['post', 'delete'])
    def bulk_assign(self, request, pk=None):
        task = self.get_object()
        person_ids = request.data.get('person_ids', [])

        if not isinstance(person_ids, list):
            return Response({'error': 'person_ids must be a list'}, status=status.HTTP_400_BAD_REQUEST)

        if request.method == 'POST':
            existing_assignments = set(
                task.assignments.values_list('person_id', flat=True))
            new_assignments = set(person_ids) - existing_assignments

            bulk_assignments = [
                PersonTask(
                    task=task,
                    person_id=person_id,
                    status=PersonTask.PENDING
                    # Basic validation
                ) for person_id in new_assignments if isinstance(person_id, int)
            ]
            if not bulk_assignments:
                return Response({'status': 'No new valid person IDs provided or all persons already assigned.'}, status=status.HTTP_200_OK)

            PersonTask.objects.bulk_create(bulk_assignments)
            return Response({'status': f'{len(bulk_assignments)} Tasks assigned successfully.'})

        elif request.method == 'DELETE':
            # Validate person_ids are integers
            valid_person_ids = [
                pid for pid in person_ids if isinstance(pid, int)]
            if not valid_person_ids:
                return Response({'error': 'No valid person IDs provided for deletion.'}, status=status.HTTP_400_BAD_REQUEST)

            deleted_count, _ = PersonTask.objects.filter(
                task=task,
                person_id__in=valid_person_ids
            ).delete()

            if deleted_count == 0:
                return Response({'status': 'No matching assignments found for the provided person IDs.'}, status=status.HTTP_404_NOT_FOUND)

            return Response({'status': f'{deleted_count} Task assignments deleted successfully.'})

    @action(detail=True, methods=['get'])
    def completion_stats(self, request, pk=None):
        task = self.get_object()
        total = task.assignments.count()
        completed = task.assignments.filter(
            status=PersonTask.COMPLETED).count()
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
        pk = self.kwargs.get('task_pk')
        if pk:
            return PersonTask.objects.filter(task_id=pk)

        pk = self.kwargs.get('pk')
        if pk:
            return PersonTask.objects.filter(id=pk)

        return PersonTask.objects.all()

    @action(detail=True, methods=['post'])
    def mark_completed(self, request, pk=None):
        person_task = self.get_object()
        if person_task.status == PersonTask.COMPLETED:
            return Response(
                {'error': 'This task is already completed'},
                status=status.HTTP_400_BAD_REQUEST
            )

        person_task.mark_completed(request.user)
        serializer = self.get_serializer(person_task)
        return Response(
            {
                'success': True,
                'message': 'Task marked as completed',
                'person_task': serializer.data
            }
        )
