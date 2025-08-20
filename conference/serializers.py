from datetime import timedelta
from django.utils import timezone
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer
from django.contrib.auth import get_user_model

from conference.models import Conference, ConferenceRole, ConferencePermission, ConferenceMember, ConferenceInvitation

User = get_user_model()


class ConferenceSerializer(ModelSerializer):
    days_duration = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()

    class Meta:
        model = Conference
        fields = [
            'id', 'name', 'slug', 'description', 'start_date', 'end_date', 'is_active',
            'created_by', 'days_duration'
        ]

    @staticmethod
    def get_days_duration(obj):
        from django.utils import timezone
        today = timezone.now().date()

        if today < obj.start_date:
            return {
                'status': 'upcoming',
                'days_left': (obj.start_date - today).days,
            }
        elif obj.start_date <= today <= obj.end_date:
            return {
                'status': 'ongoing',
                'days_left': (obj.end_date - today).days,
            }
        else:
            return {
                'status': 'ended',
                'days_left': 0,
            }

    def get_created_by(self, obj):
        user = self.context['request'].user
        return {
            'id': user.id,
            'username': user.username
        }


class ConferenceDetailSerializer(ModelSerializer):
    days_duration = serializers.SerializerMethodField()
    user_role = serializers.SerializerMethodField()
    user_permissions = serializers.SerializerMethodField()
    membership_status = serializers.SerializerMethodField()
    user_status_message = serializers.SerializerMethodField()

    class Meta:
        model = Conference
        fields = [
            'id', 'name', 'slug', 'description', 'start_date', 'end_date', 'is_active',
            'created_by', 'days_duration', 'max_executives', 'max_members',
            'enable_categorization', 'max_tasks_per_conference', 'max_tasks_per_user',
            'user_role', 'user_permissions', 'membership_status', 'user_status_message'
        ]
        read_only_fields = ['created_at', 'updated_at',
                            'created_by', 'user_role', 'user_permissions', 'user_status_message']

    def validate(self, data):
        if data.get('slug'):
            conference_id = self.instance.id if self.instance else None
            slug_exists = Conference.objects.filter(slug=data['slug'])
            if conference_id:
                slug_exists = slug_exists.exclude(id=conference_id)

            if slug_exists.exists():
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

        if request and request.user.is_authenticated:
            user_membership = instance.members.filter(
                user=request.user).first()

            conference_access, _ = request.user.check_conference_access(
                instance)

            if (not user_membership and not request.user.is_superuser) or not conference_access:
                allowed_fields = ['id', 'name', 'slug', 'description',
                                  'start_date', 'end_date', 'days_duration']
                if not conference_access:
                    allowed_fields.extend(
                        ['membership_status', 'user_status_message'])
                representation = {
                    k: v for k, v in representation.items() if k in allowed_fields}

        return representation

    def get_user_role(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None

        membership = obj.members.filter(
            user=request.user, status='active').first()
        return membership.role.name if membership else None

    def get_user_permissions(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return []

        if request.user.is_superuser:
            return list(ConferencePermission.objects.values_list('codename', flat=True))

        membership = obj.members.filter(
            user=request.user, status='active').first()
        if membership:
            return list(membership.role.permissions.values_list('codename', flat=True))

        return []

    def get_membership_status(self, obj):
        """Get membership status for current user"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None

        membership = obj.members.filter(user=request.user).first()
        return membership.status if membership else None

    def get_user_status_message(self, obj):
        """Get status message for current user's membership"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None

        if request.user.is_superuser:
            return None

        try:
            membership = obj.members.get(user=request.user)
            return membership.get_status_message()
        except:
            return "You are not a member of this conference."

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


class ConferencePermissionSerializer(ModelSerializer):
    class Meta:
        model = ConferencePermission
        fields = ['id', 'codename', 'name', 'description']


class ConferenceRoleSerializer(ModelSerializer):
    permissions = ConferencePermissionSerializer(many=True, read_only=True)
    permission_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        help_text="List of permission IDs to assign to this role"
    )

    class Meta:
        model = ConferenceRole
        fields = [
            'id', 'role_type', 'name', 'description', 'permissions',
            'permission_ids', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def create(self, validated_data):
        permission_ids = validated_data.pop('permission_ids', [])
        role = super().create(validated_data)

        if permission_ids:
            permissions = ConferencePermission.objects.filter(
                id__in=permission_ids)
            role.permissions.set(permissions)

        return role

    def update(self, instance, validated_data):
        permission_ids = validated_data.pop('permission_ids', None)
        role = super().update(instance, validated_data)

        if permission_ids is not None:
            permissions = ConferencePermission.objects.filter(
                id__in=permission_ids)
            role.permissions.set(permissions)

        return role


class ConferenceMemberSerializer(ModelSerializer):
    user_username = serializers.CharField(
        source='user.username', read_only=True)
    user_full_name = serializers.CharField(
        source='user.get_full_name', read_only=True)
    role_name = serializers.CharField(source='role.name', read_only=True)
    role_type = serializers.CharField(source='role.role_type', read_only=True)
    status_message = serializers.SerializerMethodField()
    can_perform_actions = serializers.SerializerMethodField()

    class Meta:
        model = ConferenceMember
        fields = [
            'id', 'user', 'user_username', 'user_full_name', 'role', 'role_name',
            'role_type', 'status', 'status_message', 'can_perform_actions', 'joined_at', 'updated_at'
        ]
        read_only_fields = ['joined_at', 'updated_at',
                            'status_message', 'can_perform_actions']

    def get_status_message(self, obj):
        """Get user-friendly status message"""
        return obj.get_status_message()

    def get_can_perform_actions(self, obj):
        """Check if member can perform actions"""
        return obj.can_perform_actions()

    def validate(self, data):
        user = data.get('user')
        conference = self.context['conference']
        if not user or not conference:
            raise serializers.ValidationError(
                "User and conference must be provided.")
        return data


class ConferenceInvitationSerializer(ModelSerializer):
    invited_user_username = serializers.CharField(
        write_only=True,
        help_text="Username of the user to invite"
    )
    invited_user_display = serializers.CharField(
        source='invited_user.username', read_only=True)
    invited_by_display = serializers.CharField(
        source='invited_by.username', read_only=True)
    role_name = serializers.CharField(source='role.name', read_only=True)
    conference_name = serializers.CharField(
        source='conference.name', read_only=True)
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = ConferenceInvitation
        fields = [
            'id', 'conference', 'conference_name', 'invited_user', 'invited_user_username',
            'invited_user_display', 'invited_by', 'invited_by_display', 'role', 'role_name',
            'message', 'status', 'expires_at', 'responded_at', 'created_at', 'is_expired'
        ]
        read_only_fields = [
            'conference', 'invited_user', 'invited_by', 'responded_at', 'created_at',
            'invited_user_display', 'invited_by_display', 'role_name', 'conference_name', 'is_expired'
        ]

    def validate_invited_user_username(self, value):
        """Validate that the username exists"""
        try:
            user = User.objects.get(username=value)
            return user
        except User.DoesNotExist:
            raise serializers.ValidationError(
                "User with this username does not exist.")

    def validate_expires_at(self, value):
        if value and value <= timezone.now():
            raise serializers.ValidationError(
                "Expiration date must be in the future.")
        return value

    def validate_empty_values(self, data):
        if not data.get('expires_at'):
            data['expires_at'] = timezone.now() + timedelta(days=7)
        return super().validate_empty_values(data)

    def validate(self, data):
        username = data.get('invited_user_username')
        invited_by = self.context.get('request').user
        conference = data.get('conference')
        status = data.get('status')

        if invited_by == username:
            raise serializers.ValidationError(
                "The invited member can't same with inviter")

        if ConferenceMember.objects.filter(user=username, conference=conference).exists():
            raise serializers.ValidationError(
                'User is already a member of this conference.')

        if status == 'pending':
            existing_pending = ConferenceInvitation.objects.filter(
                conference=conference,
                invited_user=username,
                status='pending'
            ).exclude(pk=self.instance)
            if existing_pending.exists():
                raise serializers.ValidationError(
                    'User already has a pending invitation for this conference.')

        return data

    def create(self, validated_data):
        invited_user = validated_data.pop('invited_user_username', None)
        invited_by = self.context['request'].user
        if invited_user:
            validated_data['invited_user'] = invited_user
        validated_data['invited_by'] = invited_by
        return super().create(validated_data)

    def get_is_expired(self, obj):
        from django.utils import timezone
        return timezone.now() > obj.expires_at and obj.status == 'pending'
