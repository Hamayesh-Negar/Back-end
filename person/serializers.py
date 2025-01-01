from rest_framework import serializers

from person.models import Person, Category


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'conference']


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
