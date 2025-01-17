from django.contrib.auth import password_validation
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
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

    def validate_phone(self, value):
        if value:
            normalized_phone = value.strip().replace(' ', '')
            if not normalized_phone.startswith('+'):
                normalized_phone = f'+{normalized_phone}'

            if User.objects.filter(phone=normalized_phone).exclude(
                    id=getattr(self.instance, 'id', None)
            ).exists():
                raise serializers.ValidationError("This phone number is already in use.")

            return normalized_phone
        return value

    def validate_email(self, value):
        if value:
            normalized_email = value.lower().strip()
            if User.objects.filter(email=normalized_email).exclude(
                    id=getattr(self.instance, 'id', None)
            ).exists():
                raise serializers.ValidationError("This email is already in use.")
            return normalized_email
        return value


class UserCreateSerializer(UserBaseSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    confirm_password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    class Meta(UserBaseSerializer.Meta):
        fields = UserBaseSerializer.Meta.fields + ['password', 'confirm_password']

    def validate(self, data):
        if data.get('password') != data.get('confirm_password'):
            raise serializers.ValidationError({
                'confirm_password': "Passwords do not match."
            })

        try:
            password_validation.validate_password(data.get('password'))
        except ValidationError as e:
            raise serializers.ValidationError({
                'password': list(e.messages)
            })

        request = self.context.get('request')
        if request and request.user:
            creating_user = request.user
            requested_type = data.get('user_type')

            if not creating_user.is_superuser:
                if creating_user.is_hamayesh_manager:
                    if requested_type not in [User.UserType.HAMAYESH_YAR]:
                        raise serializers.ValidationError({
                            'user_type': "Hamayesh managers can only create Hamayesh Yar accounts."
                        })
                else:
                    raise serializers.ValidationError({
                        'user_type': "You don't have permission to create users."
                    })

        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        user_type = validated_data.get('user_type')

        if user_type == User.UserType.HAMAYESH_MANAGER:
            user = User.objects.create_hamayesh_manager(**validated_data)
        elif user_type == User.UserType.HAMAYESH_YAR:
            user = User.objects.create_hamayesh_yar(**validated_data)
        else:
            user = User.objects.create_user(**validated_data)

        return user


class UserChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, style={'input_type': 'password'})
    new_password = serializers.CharField(required=True, style={'input_type': 'password'})
    confirm_new_password = serializers.CharField(required=True, style={'input_type': 'password'})

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    @staticmethod
    def validate_new_password(value):
        try:
            password_validation.validate_password(value)
        except ValidationError as e:
            raise serializers.ValidationError(str(e))

    def validate(self, data):
        if data.get('new_password') != data.get('confirm_new_password'):
            raise serializers.ValidationError({
                'detail': "Passwords do not match."
            })
        return data

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user
