from django.utils import timezone
from rest_framework import serializers

from person.models import Person, Category, PersonTask, Task
from user.models import User


class CategorySerializer(serializers.ModelSerializer):
    members_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'conference', 'name', 'description', 'members_count']

    @staticmethod
    def get_members_count(obj):
        return obj.members.count()

    def validate(self, data):
        if self.instance:
            conference = data.get('conference', self.instance.conference)
        else:
            conference = data.get('conference')

        if Category.objects.filter(conference=conference, name=data['name']).exclude(
                id=getattr(self.instance, 'id', None)).exists():
            raise serializers.ValidationError({"name": "Category with this name already exists in the conference"})
        return data


class PersonSerializer(serializers.ModelSerializer):
    categories = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), many=True)
    registered_by = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False)
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    task_count = serializers.SerializerMethodField()
    completed_task_count = serializers.SerializerMethodField()

    class Meta:
        model = Person
        fields = ['id', 'conference', 'categories', 'first_name',
                  'last_name', 'full_name', 'unique_code', 'hashed_unique_code', 'email', 'telephone',
                  'is_active', 'task_count', 'completed_task_count', 'registered_by']
        read_only_fields = ['registered_by', 'hashed_unique_code']

    def create(self, validated_data):
        categories = validated_data.pop('categories', [])
        validated_data['registered_by'] = self.context['request'].user
        instance = super().create(validated_data)
        instance.categories.set(categories)
        return instance

    def update(self, instance, validated_data):
        categories = validated_data.pop('categories')
        instance = super().update(instance, validated_data)
        instance.categories.set(categories)
        return instance

    def validate_unique_code(self, value):
        if value:
            if Person.objects.filter(
                    unique_code=value
            ).exclude(id=self.instance.id if self.instance else None).exists():
                raise serializers.ValidationError("This unique code is already in use.")
        return value

    def validate(self, data):
        if 'categories' in data and 'conference' in data:
            invalid_categories = [
                cat for cat in data['categories']
                if cat.conference_id != data['conference'].id
            ]
            if invalid_categories:
                raise serializers.ValidationError({
                    'categories': 'All categories must belong to the same conference'
                })
        return data

    @staticmethod
    def get_task_count(obj):
        return obj.tasks.count()

    @staticmethod
    def get_completed_task_count(obj):
        return obj.tasks.filter(status=PersonTask.COMPLETED).count()


class TaskSerializer(serializers.ModelSerializer):
    conference_name = serializers.CharField(source='conference.name', read_only=True)
    assignment_count = serializers.SerializerMethodField()
    completion_rate = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            'id', 'conference', 'name', 'description', 'is_required',
            'is_active', 'due_date', 'conference_name', 'assignment_count',
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

    @staticmethod
    def validate_due_date(value):
        if value and value < timezone.now():
            raise serializers.ValidationError(
                "Due date cannot be in the past"
            )
        return value

    def validate(self, data):
        conference = data['conference']
        name = data['name']
        if Task.objects.filter(conference=conference, name=name).exists():
            raise serializers.ValidationError({"name": "Task with this name already exists in the conference"})
        return data


class PersonTaskSerializer(serializers.ModelSerializer):
    person_name = serializers.CharField(source='person.get_full_name', read_only=True)
    task_name = serializers.CharField(source='task.name', read_only=True)

    class Meta:
        model = PersonTask
        fields = [
            'id', 'person', 'task', 'status', 'notes', 'completed_at',
            'completed_by', 'person_name', 'task_name'
        ]
        read_only_fields = ['completed_at', 'completed_by']

    def validate(self, data):
        if self.instance and data.get('status') == PersonTask.COMPLETED:
            if self.instance.status == PersonTask.COMPLETED:
                raise serializers.ValidationError({
                    'status': 'Task is already marked as completed'
                })

            request = self.context.get('request')
            if request and request.user:
                data['completed_by'] = request.user
                data['completed_at'] = timezone.now()

        if 'task' in data and 'person' in data:
            if data['task'].conference_id != data['person'].conference_id:
                raise serializers.ValidationError({
                    'task': 'Task must belong to the same conference as the person'
                })

        return data
