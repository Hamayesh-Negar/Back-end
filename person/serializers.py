from django.utils import timezone
from rest_framework import serializers

from person.models import Person, Category, PersonTask, Task
from user.models import User


class CategorySerializer(serializers.ModelSerializer):
    members_count = serializers.SerializerMethodField()
    tasks = serializers.PrimaryKeyRelatedField(
        queryset=Task.objects.all(),
        many=True,
        required=False,
    )
    task_names = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'conference', 'name', 'description', 'tasks',
                  'task_names', 'members_count', 'created_at', 'updated_at']
        read_only_fields = ['task_names',
                            'members_count', 'created_at', 'updated_at']

    @staticmethod
    def get_members_count(obj):
        return obj.members.count()

    @staticmethod
    def get_task_names(obj):
        return [{"id": task.id, "name": task.name} for task in obj.tasks.all()]

    def validate(self, data):
        if self.instance:
            conference = data.get('conference', self.instance.conference)
        else:
            conference = data.get('conference')

        if Category.objects.filter(conference=conference, name=data['name']).exclude(
                id=getattr(self.instance, 'id', None)).exists():
            raise serializers.ValidationError(
                {"name": "دسته‌بندی با این نام در رویداد وجود دارد"})
        return data


class PersonCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']
        read_only_fields = ['id', 'name']


class PersonSerializer(serializers.ModelSerializer):
    categories = serializers.SerializerMethodField()
    tasks = serializers.PrimaryKeyRelatedField(
        queryset=Task.objects.all(),
        many=True,
        required=False,
        write_only=True,
    )
    registered_by = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False)
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    task_count = serializers.SerializerMethodField()
    completed_task_count = serializers.SerializerMethodField()
    assignments = serializers.SerializerMethodField()

    class Meta:
        model = Person
        fields = ['id', 'categories', 'tasks', 'first_name',
                  'last_name', 'full_name', 'unique_code', 'email', 'telephone', 'gender',
                  'is_active', 'task_count', 'assignments', 'completed_task_count', 'registered_by']
        read_only_fields = ['registered_by', 'full_name', 'categories',
                            'task_count', 'completed_task_count']

    def get_categories(self, obj):
        categories = obj.categories.all()
        return [
            {
                'id': cat.id,
                'name': cat.name,
                'description': cat.description
            }
            for cat in categories
        ]

    def get_task_count(self, obj):
        return obj.tasks.count()

    def get_completed_task_count(self, obj):
        return obj.tasks.filter(status=PersonTask.COMPLETED).count()

    def get_assignments(self, obj):
        assignments = PersonTask.objects.filter(person=obj)
        return PersonTaskSerializer(assignments, many=True).data

    def create(self, validated_data):
        validated_data.pop('categories', [])
        validated_data.pop('tasks', [])
        user = self.context['request'].user
        validated_data['registered_by'] = user
        if hasattr(user, 'preference') and user.preference.selected_conference:
            validated_data['conference'] = user.preference.selected_conference
        instance = super().create(validated_data)
        return instance

    def update(self, instance, validated_data):
        validated_data.pop('categories', None)
        validated_data.pop('tasks', None)
        instance = super().update(instance, validated_data)
        return instance

    def validate_unique_code(self, value):
        if value:
            if Person.objects.filter(
                    unique_code=value
            ).exclude(id=self.instance.id if self.instance else None).exists():
                raise serializers.ValidationError(
                    {"error": "این کد منحصر به فرد قبلاً استفاده شده است."})
        return value

    def validate(self, data):
        conference = data.get('conference')
        if not conference and self.instance:
            conference = self.instance.conference

        if 'categories' in data and conference:
            invalid_categories = [
                cat for cat in data['categories']
                if cat.conference_id != conference.id
            ]
            if invalid_categories:
                raise serializers.ValidationError({
                    'categories': 'تمام دسته‌بندی‌ها باید متعلق به همان رویداد باشند'
                })

        if 'tasks' in data and conference:
            invalid_tasks = [
                task for task in data['tasks']
                if task.conference_id != conference.id
            ]
            if invalid_tasks:
                raise serializers.ValidationError({
                    'tasks': 'تمام وظایف باید متعلق به همان رویداد باشند'
                })
        return data


class PersonListSerializer(serializers.ModelSerializer):
    categories = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), many=True)
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    task_count = serializers.SerializerMethodField()
    completed_task_count = serializers.SerializerMethodField()

    class Meta:
        model = Person
        fields = [
            'id', 'categories', 'full_name', 'unique_code', 'is_active',
            'task_count', 'completed_task_count'
        ]
        read_only_fields = ['categories',
                            'full_name', 'unique_code', 'is_active']

    @staticmethod
    def get_task_count(obj):
        return obj.tasks.count()

    @staticmethod
    def get_completed_task_count(obj):
        return obj.tasks.filter(status=PersonTask.COMPLETED).count()


class TaskSerializer(serializers.ModelSerializer):
    assignment_count = serializers.SerializerMethodField()
    completion_rate = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            'id', 'conference', 'name', 'description', 'is_required',
            'is_active', 'started_time', 'finished_time', 'order', 'assignment_count',
            'completion_rate', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    @staticmethod
    def get_assignment_count(obj):
        return obj.assignments.count()

    @staticmethod
    def get_completion_rate(obj):
        total = obj.assignments.count()
        if total == 0:
            return 0
        completed = obj.assignments.filter(status=PersonTask.COMPLETED).count()
        return round((completed / total) * 100, 2)

    def validate(self, data):
        conference = data['conference']
        name = data['name']
        if Task.objects.filter(conference=conference, name=name).exclude(
                id=getattr(self.instance, 'id', None)).exists():
            raise serializers.ValidationError(
                'وظیفه‌ای با این نام در این رویداد وجود دارد.')

        started_time = data['started_time']
        finished_time = data['finished_time']
        if started_time is not None and finished_time is not None:
            if started_time > finished_time:
                raise serializers.ValidationError(
                    'زمان شروع نمی‌تواند بعد از زمان پایان باشد.')

        return data


class PersonTaskSerializer(serializers.ModelSerializer):
    task_name = serializers.CharField(source='task.name', read_only=True)

    class Meta:
        model = PersonTask
        fields = [
            'id', 'task', 'status', 'notes', 'completed_at',
            'completed_by', 'task_name'
        ]
        read_only_fields = ['completed_at', 'completed_by']

    def create(self, validated_data):
        person = self.context.get('person') or validated_data.get('person')
        if person:
            validated_data['person'] = person
        return super().create(validated_data)

    def validate(self, data):
        if 'task' in data and 'person' in data:
            if data['task'].conference_id != data['person'].conference_id:
                raise serializers.ValidationError({
                    'error': 'وظیفه باید متعلق به همان رویدادی باشد که شخص در آن شرکت دارد.'
                })

        if not self.instance:
            person = data.get('person')
            task = data.get('task')
            if person and task and PersonTask.objects.filter(person=person, task=task).exists():
                raise serializers.ValidationError(
                    {"error": "این وظیفه قبلاً به این شخص اختصاص داده شده است."})

        if self.instance and data.get('status') == PersonTask.COMPLETED:
            if self.instance.status == PersonTask.COMPLETED:
                raise serializers.ValidationError({
                    'error': 'این وظیفه قبلاً به عنوان تکمیل شده علامت گذاری شده است.'
                })

            request = self.context.get('request')
            if request and request.user:
                data['completed_by'] = request.user
                data['completed_at'] = timezone.now()
        return data
