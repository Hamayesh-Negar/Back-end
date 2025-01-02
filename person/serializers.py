from rest_framework import serializers

from person.models import Person, Category


class CategorySerializer(serializers.ModelSerializer):
    members_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'conference', 'name', 'description', 'members_count', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

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
    # categories = CategorySerializer(many=True, read_only=False)

    class Meta:
        model = Person
        fields = ['id', 'conference', 'categories', 'first_name',
                  'last_name', 'unique_code', 'email', 'telephone',
                  'is_active', 'registered_by', 'created_at', 'updated_at']
        read_only_fields = ['registered_by', 'created_at', 'updated_at']

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
