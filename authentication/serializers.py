from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ['id', 'email', 'phone', 'first_name', 'last_name', 'password']

    def create(self, validated_data):
        user = User.objects.create(**validated_data)
        return user
