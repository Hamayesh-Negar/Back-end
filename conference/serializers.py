from rest_framework.serializers import ModelSerializer

from conference.models import Conference
from user.serializers import UserSerializer


class ConferenceSerializer(ModelSerializer):
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = Conference
        fields = ['id', 'name', 'description', 'start_date',
                  'end_date', 'is_active', 'created_by']

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        request = self.context.get('request')
        if not request.user.is_superuser:
            representation.pop('is_active', None)
        return representation
