from asgiref.sync import async_to_sync

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from person.models import Person, Category, PersonTask, Task
from person.pagination import LargeResultsSetPagination, StandardResultsSetPagination
from person.serializers import PersonListSerializer, PersonSerializer, CategorySerializer, TaskSerializer, PersonTaskSerializer
from person.async_utils import create_person, update_person


class PersonViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend,
                       filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['first_name', 'last_name',
                     'telephone', 'email', 'unique_code']
    ordering_fields = ['created_at']
    pagination_class = LargeResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'preference') and user.preference.selected_conference:
            return Person.objects.filter(conference=user.preference.selected_conference.id)

    def get_serializer_class(self):
        if self.action == 'list':
            return PersonListSerializer
        return PersonSerializer

    def create(self, request, *args, **kwargs):
        from person.async_utils import get_user_conference

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        conference = serializer.validated_data.get('conference')
        if not conference:
            conference = async_to_sync(get_user_conference)(request.user)
            if not conference:
                return Response(
                    {'error': 'آیدی رویداد الزامی است'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            serializer.validated_data['conference'] = conference

        person = async_to_sync(create_person)(
            {
                'conference': serializer.validated_data['conference'],
                'first_name': serializer.validated_data['first_name'],
                'last_name': serializer.validated_data['last_name'],
                'email': serializer.validated_data.get('email'),
                'telephone': serializer.validated_data.get('telephone'),
                'gender': serializer.validated_data.get('gender', 'male'),
                'unique_code': serializer.validated_data.get('unique_code', ''),
            },
            serializer.validated_data.get('categories', []),
            request.user
        )

        return Response(
            PersonSerializer(person, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()

        serializer = self.get_serializer(
            instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        person_data = {k: v for k, v in serializer.validated_data.items()
                       if k not in ['conference', 'registered_by', 'categories']}

        categories_data = serializer.validated_data.get('categories')

        person = async_to_sync(update_person)(
            instance, person_data, categories_data)

        return Response(
            PersonSerializer(person, context={'request': request}).data
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def toggle_active(self, request, pk=None):
        person = self.get_object()
        person.is_active = not person.is_active
        person.save()

        message = 'فعال شد' if person.is_active else 'غیرفعال شد'
        return Response(
            {
                'success': True,
                'message': f'کاربر با موفقیت {message}',
                'person': self.get_serializer(person).data
            }
        )

    @action(detail=True, methods=['get'])
    async def tasks_summary(self, request, pk=None):
        from person.async_utils import get_person_tasks_count

        person = self.get_object()
        summary = await get_person_tasks_count(person)
        return Response(summary)

    @action(detail=False, methods=['post'])
    async def validate_unique_code(self, request):
        from person.async_utils import get_person_by_hashed_code

        hashed_unique_code = request.data.get('hashed_unique_code')

        if not hashed_unique_code:
            return Response({'error': 'کد منحصر به فرد الزامی است'})

        person = await get_person_by_hashed_code(hashed_unique_code)
        if not person:
            return Response(
                {'error': 'فردی با این کد منحصر به فرد وجود ندارد'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.get_serializer(person)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    async def submit_task(self, request):
        from person.async_utils import (
            get_person_by_hashed_code,
            get_task_by_id,
            get_person_task,
            mark_person_task_completed
        )

        hashed_unique_code = request.data.get('hashed_unique_code')
        task_id = request.data.get('task_id')

        if not hashed_unique_code:
            return Response({'error': 'کد منحصر به فرد الزامی است'})

        if not task_id:
            return Response({'error': 'آیدی وظیفه الزامی است'})

        person = await get_person_by_hashed_code(hashed_unique_code)
        if not person:
            return Response({'error': 'فردی با این کد منحصر به فرد وجود ندارد'})

        if not person.is_active:
            return Response({
                'error': 'فرد فعال نیست، لطفاً با مدیر رویداد تماس بگیرید'
            })

        task = await get_task_by_id(task_id)
        if not task:
            return Response({'error': 'وظیفه‌ای با این آیدی وجود ندارد'})

        person_task = await get_person_task(person, task)
        if not person_task:
            return Response({'error': 'این وظیفه به این فرد اختصاص داده نشده است'})

        if person_task.status == PersonTask.COMPLETED:
            return Response({
                'error': 'این وظیفه قبلاً تکمیل شده است',
                'person_task': PersonTaskSerializer(person_task).data
            })

        person_task = await mark_person_task_completed(person_task, request.user)

        return Response({
            'success': True,
            'message': f'وظیفه "{task.name}" با موفقیت برای {person.get_full_name()} تکمیل شد',
            'person_task': PersonTaskSerializer(person_task).data
        })


class CategoryViewSet(ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend,
                       filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['members_count']
    pagination_class = LargeResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'preference') and user.preference.selected_conference:
            return Category.objects.filter(conference=user.preference.selected_conference.id)

    @action(detail=True, methods=['post'])
    async def bulk_add_members(self, request, pk=None):
        from person.async_utils import add_category_members

        category = self.get_object()
        person_ids = request.data.get('person_ids', [])

        category = await add_category_members(category, person_ids)
        return Response({
            'success': True,
            'message': 'اعضا با موفقیت اضافه شدند',
            'category': self.get_serializer(category).data
        })

    @action(detail=True, methods=['get'])
    async def members(self, request, pk=None):
        from person.async_utils import get_category_members

        category = self.get_object()
        members = await get_category_members(category)
        serializer = PersonSerializer(members, many=True)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.members.exists():
            return Response(
                {
                    'success': False,
                    'message': 'امکان حذف دسته‌بندی با اعضای موجود وجود ندارد'
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
    async def bulk_assign(self, request, pk=None):
        from person.async_utils import bulk_assign_tasks, bulk_unassign_tasks

        task = self.get_object()
        person_ids = request.data.get('person_ids', [])

        if not isinstance(person_ids, list):
            return Response(
                {'error': 'person_ids باید یک لیست باشد'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if request.method == 'POST':
            count = await bulk_assign_tasks(task, person_ids)

            if count == 0:
                return Response(
                    {'status': 'هیچ شناسه فرد جدید معتبری ارائه نشده است یا همه افراد قبلاً اختصاص داده شده‌اند.'},
                    status=status.HTTP_200_OK
                )

            return Response({'status': f'{count} وظیفه با موفقیت اختصاص داده شد.'})
        elif request.method == 'DELETE':
            deleted_count = await bulk_unassign_tasks(task, person_ids)

            if deleted_count == 0:
                return Response(
                    {'status': 'هیچ تخصیص مطابقتی برای شناسه‌های فرد ارائه شده یافت نشد.'},
                    status=status.HTTP_404_NOT_FOUND
                )

            return Response({'status': f'{deleted_count} تخصیص وظیفه با موفقیت حذف شد.'})

    @action(detail=True, methods=['get'])
    async def completion_stats(self, request, pk=None):
        from person.async_utils import get_task_completion_stats

        task = self.get_object()
        stats = await get_task_completion_stats(task)
        return Response(stats)


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
    async def mark_completed(self, request, pk=None):
        from person.async_utils import mark_person_task_completed

        person_task = self.get_object()
        if person_task.status == PersonTask.COMPLETED:
            return Response(
                {'error': 'این وظیفه قبلا انجام شده است'},
                status=status.HTTP_400_BAD_REQUEST
            )

        person_task = await mark_person_task_completed(person_task, request.user)
        serializer = self.get_serializer(person_task)
        return Response(
            {
                'success': True,
                'message': 'وظیفه انجام شد',
                'person_task': serializer.data
            }
        )
