from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from conference.models import Conference


class ConferenceSerializer(ModelSerializer):
    days_duration = serializers.SerializerMethodField()

    class Meta:
        model = Conference
        fields = ['id', 'name', 'slug', 'description', 'start_date',
                  'end_date', 'is_active', 'created_by', 'days_duration']
        read_only_fields = ['created_at', 'updated_at', 'created_by']

    def validate(self, data):
        if data.get('slug'):
            if Conference.objects.filter(slug=data['slug']).exists():
                raise serializers.ValidationError({
                    "slug": "Conference with this slug already exists"
                })

        if data.get('start_date') and data.get('end_date'):
            if data['start_date'] > data['end_date']:
                raise serializers.ValidationError({
                    "end_date": "End date must be after start date"
                })
        return data

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
