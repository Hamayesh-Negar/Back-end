from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer
from user.models import User, UserPreference


class UserSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name',
                  'phone', 'is_active']


class UserBaseSerializer(ModelSerializer):
    full_name = serializers.CharField(source='get_full_name', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'phone', 'first_name', 'last_name',
            'full_name', 'user_type',
            'is_active', 'date_joined'
        ]
        read_only_fields = ['date_joined']

    def validate_username(self, value):
        if value:
            normalized_username = value.lower().strip()
            if User.objects.filter(username=normalized_username).exclude(
                    id=getattr(self.instance, 'id', None)
            ).exists():
                raise serializers.ValidationError(
                    "این نام کاربری قبلاً استفاده شده است.")
            return normalized_username
        return value

    def validate_phone(self, value):
        if value:
            normalized_phone = value.strip().replace(' ', '')
            if not normalized_phone.startswith('+'):
                normalized_phone = f'+{normalized_phone}'

            if User.objects.filter(phone=normalized_phone).exclude(
                    id=getattr(self.instance, 'id', None)
            ).exists():
                raise serializers.ValidationError(
                    "این شماره تلفن قبلاً استفاده شده است.")

            return normalized_phone
        return value

    def validate_email(self, value):
        if value:
            normalized_email = value.lower().strip()
            if User.objects.filter(email=normalized_email).exclude(
                    id=getattr(self.instance, 'id', None)
            ).exists():
                raise serializers.ValidationError(
                    "این ایمیل قبلاً استفاده شده است.")
            return normalized_email
        return value


class UserUpdateSerializer(UserBaseSerializer):

    class Meta(UserBaseSerializer.Meta):
        fields = [
            'id', 'username', 'email', 'phone', 'first_name', 'last_name',
            'full_name', 'is_active', 'date_joined'
        ]
        read_only_fields = ['date_joined', 'full_name']

    def validate(self, data):
        request = self.context.get('request')
        if request and request.user:
            updating_user = request.user
            target_user = self.instance

            if target_user != updating_user and not updating_user.is_superuser and not updating_user.is_hamayesh_manager:
                raise serializers.ValidationError(
                    "شما اجازه ویرایش این پروفایل را ندارید.")

            if 'is_active' in data:
                if not (updating_user.is_superuser or updating_user.is_hamayesh_manager):
                    raise serializers.ValidationError(
                        "شما اجازه تغییر این فیلد را ندارید.")

        return data


class UserChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(
        required=True, style={'input_type': 'password'})
    new_password = serializers.CharField(
        required=True, style={'input_type': 'password'})
    confirm_new_password = serializers.CharField(
        required=True, style={'input_type': 'password'})

    def validate_old_password(self, value):
        user = self.context.get('user') or self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("رمزعبور فعلی نادرست است.")
        return value

    @staticmethod
    def validate_new_password(value):
        try:
            password_validation.validate_password(value)
        except ValidationError as e:
            raise serializers.ValidationError(str(e))

    def validate(self, data):
        if data.get('new_password') != data.get('confirm_new_password'):
            raise serializers.ValidationError(
                "رمزعبور با تأیید رمزعبور مطابقت ندارد.")
        return data

    def save(self, **kwargs):
        user = self.context.get('user') or self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class UserPreferenceSerializer(ModelSerializer):
    selected_conference_name = serializers.CharField(
        source='selected_conference.name',
        read_only=True
    )

    class Meta:
        model = UserPreference
        fields = [
            'id',
            'user',
            'selected_conference',
            'selected_conference_name',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['user', 'created_at', 'updated_at']

    def validate_selected_conference(self, value):
        if value:
            user = self.context.get(
                'request').user if self.context.get('request') else None
            if user:
                has_access, message = user.check_conference_access(value)
                if not has_access:
                    raise serializers.ValidationError(
                        f"شما به این رویداد دسترسی ندارید: {message}"
                    )
        return value
