from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from user.models import User


class UserSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name',
                  'phone', 'user_type', 'is_active', 'date_joined']


class UserBaseSerializer(ModelSerializer):
    full_name = serializers.CharField(source='get_full_name', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'email', 'phone', 'first_name', 'last_name',
            'full_name', 'user_type', 'user_type',
            'is_active', 'date_joined'
        ]
        read_only_fields = ['date_joined']

    def validate_email(self, value):
        if value:
            normalized_email = value.lower().strip()
            if User.objects.filter(email=normalized_email).exclude(
                    id=getattr(self.instance, 'id', None)
            ).exists():
                raise serializers.ValidationError("This email is already in use.")
            return normalized_email
        return value
