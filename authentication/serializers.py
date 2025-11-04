from django.contrib.auth import get_user_model, authenticate
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.utils import timezone

User = get_user_model()


class RegisterSerializer(ModelSerializer):
    password = serializers.CharField(
        write_only=True, required=True,  min_length=8, style={'input_type': 'password'})
    confirm_password = serializers.CharField(
        write_only=True, required=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'phone', 'first_name', 'last_name', 'password', 'confirm_password'
                  ]
        extra_kwargs = {
            'username': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
            'email': {'required': True},
        }

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError(
                "رمزعبور با تأیید رمزعبور مطابقت ندارد.")
        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password', None)
        password = validated_data.pop('password', None)

        user = User.objects.create(**validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()

    def validate(self, data):
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            raise serializers.ValidationError(
                "هر دو فیلد نام کاربری و رمزعبور الزامی هستند.")

        user = authenticate(username=username, password=password)

        if not user:
            raise serializers.ValidationError(
                "نام کاربری یا رمزعبور نامعتبر است.")

        if not user.is_active:
            raise serializers.ValidationError("حساب کاربری غیرفعال است.")

        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])

        return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, data):
        data = super().validate(data)
        return data
