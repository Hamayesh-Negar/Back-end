from rest_framework import serializers

from person.models import Person, Category


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
    full_name = serializers.CharField(source='get_full_name', read_only=True)

    class Meta:
        model = Person
        fields = ['id', 'conference', 'categories', 'first_name',
                  'last_name', 'full_name', 'unique_code', 'hashed_unique_code', 'email', 'telephone',
                  'is_active', 'registered_by']
        read_only_fields = ['registered_by', 'hashed_unique_code']

    def create(self, validated_data):
        categories = validated_data.pop('categories', [])
        validated_data['registered_by'] = self.context['request'].user
        instance = super().create(validated_data)
        instance.categories.set(categories)
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        request = self.context.get('request')
        if request.user.is_hamayesh_yar:
            representation.pop('is_active', None)
        return representation

    def validate_unique_code(self, value):
        if value:
            if Person.objects.filter(
                    unique_code=value
            ).exclude(id=self.instance.id if self.instance else None).exists():
                raise serializers.ValidationError("This unique code is already in use.")
        return value
