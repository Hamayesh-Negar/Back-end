from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from conference.models import Conference


class ConferenceSerializer(ModelSerializer):
    days_duration = serializers.SerializerMethodField()

    class Meta:
        model = Conference
        fields = ['id', 'name', 'description', 'start_date',
                  'end_date', 'is_active', 'created_by', 'days_duration']
        read_only_fields = ['created_at', 'updated_at', 'created_by']

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        request = self.context.get('request')
        if not request.user.is_superuser:
            representation.pop('is_active', None)
        return representation

    @staticmethod
    def get_days_duration(obj):
        from django.utils import timezone
        today = timezone.now().date()

        if today < obj.start_date:
            return {
                'status': 'upcoming',
                'days_left': (obj.start_date - today).days,
                'message': f'Starts in {(obj.start_date - today).days} days'
            }
        elif obj.start_date <= today <= obj.end_date:
            return {
                'status': 'ongoing',
                'days_left': (obj.end_date - today).days,
                'message': f'Ends in {(obj.end_date - today).days} days'
            }
        else:
            return {
                'status': 'ended',
                'days_left': 0,
                'message': 'Conference has ended'
            }
