from django.contrib.auth import get_user_model, authenticate
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

User = get_user_model()


class RegisterSerializer(ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ['id', 'email', 'phone', 'first_name', 'last_name', 'password']

    def create(self, validated_data):
        user = User.objects.create(**validated_data)
        return user


class LoginSerializer(ModelSerializer):
    email = serializers.CharField(required=True)
    password = serializers.CharField(required=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ['email', 'password']

    def validate(self, data):
        # email = data.get('email')
        # password = data.get('password')
        # user = User.objects.filter(email=email).first()
        user = authenticate(**data)
        if user and user.is_active:
            return user
        raise serializers.ValidationError("Invalid email or password or account is not active.")
