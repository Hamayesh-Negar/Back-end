from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

User = get_user_model()


class Conference(models.Model):
    name = models.CharField(help_text='Conference name', max_length=75)
    slug = models.SlugField(max_length=100, unique=True,
                            blank=True, help_text='Conference slug')
    description = models.TextField(
        help_text='Conference description', null=True, blank=True)
    start_date = models.DateField(help_text='Conference start date')
    end_date = models.DateField(help_text='Conference end date')
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        'user.User', on_delete=models.SET_NULL, null=True, editable=False)

    max_executives = models.PositiveIntegerField(
        default=10, help_text='Maximum number of executive staff members')
    max_members = models.PositiveIntegerField(
        default=1000, help_text='Maximum number of conference members')
    enable_categorization = models.BooleanField(
        default=True, help_text='Enable content categorization')
    max_tasks_per_conference = models.PositiveIntegerField(
        default=100, help_text='Maximum number of tasks per conference')
    max_tasks_per_user = models.PositiveIntegerField(
        default=10, help_text='Maximum number of tasks assignable per user')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "conferences"
        ordering = ['-start_date']
        permissions = [
            ("edit_all_fields", "Can edit all conference fields"),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
            org_slug = self.slug
            if Conference.objects.filter(slug=self.slug).exists():
                self.slug = f"{org_slug}-{self.id}"
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()

        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError(
                {'end_date': 'End date must be after start date.'})

        if self.pk:
            current_members = self.members.count()
            if current_members > self.max_members:
                raise ValidationError(
                    {'max_members': f'Cannot reduce max members below current count ({current_members}).'})

            current_executives = self.members.filter(
                role__role_type__in=['secretary', 'deputy', 'assistant']).count()
            if current_executives > self.max_executives:
                raise ValidationError(
                    {'max_executives': f'Cannot reduce max executives below current count ({current_executives}).'})


class ConferencePermission(models.Model):
    codename = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Conference Permission'
        verbose_name_plural = 'Conference Permissions'
        ordering = ['codename']

    def __str__(self):
        return f"{self.name} ({self.codename})"


class ConferenceRole(models.Model):
    ROLE_TYPES = [
        ('secretary', 'Conference Secretary'),
        ('deputy', 'Conference Deputy'),
        ('assistant', 'Conference Assistant'),
    ]

    conference = models.ForeignKey(
        Conference, on_delete=models.CASCADE, related_name='roles')
    role_type = models.CharField(max_length=20, choices=ROLE_TYPES)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(
        ConferencePermission, blank=True, related_name='roles')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Conference Role'
        verbose_name_plural = 'Conference Roles'
        unique_together = ['conference', 'role_type']
        ordering = ['conference', 'role_type']

    def __str__(self):
        return f"{self.name} - {self.conference.name}"

    def clean(self):
        super().clean()

        if self.role_type == 'secretary':
            existing_secretary = ConferenceRole.objects.filter(
                conference=self.conference,
                role_type='secretary'
            ).exclude(pk=self.pk)
            if existing_secretary.exists():
                raise ValidationError(
                    {'role_type': 'Only one Secretary role is allowed per conference.'})


class ConferenceMember(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='conference_memberships')
    conference = models.ForeignKey(
        Conference, on_delete=models.CASCADE, related_name='members')
    role = models.ForeignKey(
        ConferenceRole, on_delete=models.CASCADE, related_name='members')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='active')
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Conference Member'
        verbose_name_plural = 'Conference Members'
        unique_together = ['user', 'conference']
        ordering = ['conference', 'role__role_type', 'user__username']

    def __str__(self):
        return f"{self.user.username} - {self.role.name} in {self.conference.name}"

    def clean(self):
        super().clean()

        if not self.pk:
            current_members = self.conference.members.count()
            if current_members >= self.conference.max_members:
                raise ValidationError(
                    'Conference has reached maximum member limit.')

        if self.role.role_type in ['secretary', 'deputy', 'assistant']:
            current_executives = self.conference.members.filter(
                role__role_type__in=['secretary', 'deputy', 'assistant']
            ).count()
            if not self.pk and current_executives >= self.conference.max_executives:
                raise ValidationError(
                    'Conference has reached maximum executive limit.')

        if self.role.role_type == 'secretary':
            existing_secretary = ConferenceMember.objects.filter(
                conference=self.conference,
                role__role_type='secretary'
            ).exclude(pk=self.pk)
            if existing_secretary.exists():
                raise ValidationError(
                    'Only one Secretary is allowed per conference.')

    def has_permission(self, permission_codename):
        if self.status != 'active':
            return False
        return self.role.permissions.filter(codename=permission_codename).exists()

    def get_permissions(self):
        return self.role.permissions.all()

    def get_status_message(self):
        if self.status == 'active':
            return None
        elif self.status == 'suspended':
            return f"Your membership in '{self.conference.name}' has been suspended."
        elif self.status == 'inactive':
            return f"Your membership in '{self.conference.name}' is inactive."
        return f"Your membership status is '{self.status}'."

    def can_perform_actions(self):
        return self.status == 'active'


class ConferenceInvitation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    ]

    conference = models.ForeignKey(
        Conference, on_delete=models.CASCADE, related_name='invitations')
    invited_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='conference_invitations')
    invited_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='sent_invitations')
    role = models.ForeignKey(
        ConferenceRole, on_delete=models.CASCADE, related_name='invitations')
    message = models.TextField(
        blank=True, help_text='Optional invitation message')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending')
    expires_at = models.DateTimeField(help_text='Invitation expiration date')
    responded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Conference Invitation'
        verbose_name_plural = 'Conference Invitations'
        ordering = ['-created_at']

    def __str__(self):
        return f"Invitation to {self.invited_user.username} for {self.conference.name}"

    def clean(self):
        super().clean()

        if ConferenceMember.objects.filter(user=self.invited_user, conference=self.conference).exists():
            raise ValidationError(
                'User is already a member of this conference.')

        if self.status == 'pending':
            existing_pending = ConferenceInvitation.objects.filter(
                conference=self.conference,
                invited_user=self.invited_user,
                status='pending'
            ).exclude(pk=self.pk)
            if existing_pending.exists():
                raise ValidationError(
                    'User already has a pending invitation for this conference.')

    def accept(self):
        if self.status != 'pending':
            raise ValidationError('Only pending invitations can be accepted.')

        if timezone.now() > self.expires_at:
            self.status = 'expired'
            self.save()
            raise ValidationError('Invitation has expired.')

        member = ConferenceMember.objects.create(
            user=self.invited_user,
            conference=self.conference,
            role=self.role
        )

        self.status = 'accepted'
        self.responded_at = timezone.now()
        self.save()

        return member

    def reject(self):
        if self.status != 'pending':
            raise ValidationError('Only pending invitations can be rejected.')

        self.status = 'rejected'
        self.responded_at = timezone.now()
        self.save()


@receiver(post_save, sender=Conference)
def update_conference_status(sender, instance, **kwargs):
    today = timezone.now().date()

    if today > instance.end_date and instance.is_active:
        Conference.objects.filter(pk=instance.pk).update(is_active=False)


@receiver(post_save, sender=Conference)
def create_default_roles_and_permissions(sender, instance, created, **kwargs):
    if created:
        default_permissions = [
            ('view_conference', 'View conference details',
             'Can view basic conference information'),
            ('edit_conference', 'Edit conference settings',
             'Can modify conference settings and details'),
            ('delete_conference', 'Delete conference',
             'Can delete the entire conference'),
            ('invite_members', 'Invite conference members',
             'Can send invitations to new members'),
            ('remove_members', 'Remove conference members',
             'Can remove members from the conference'),
            ('add_people', 'Add people to conference',
             'Can add new people/attendees to the conference'),
            ('edit_people', 'Edit people information',
             'Can modify people/attendees information'),
            ('approve_people', 'Approve people registration',
             'Can approve people registration requests'),
            ('create_tasks', 'Create tasks',
             'Can create new tasks within the conference'),
            ('assign_tasks', 'Assign tasks',
             'Can assign tasks to conference members'),
            ('edit_tasks', 'Edit tasks', 'Can modify existing tasks'),
            ('view_reports', 'View conference reports',
             'Can access conference reports and analytics'),
            ('manage_categories', 'Manage conference categories',
             'Can create and manage conference categories'),
        ]

        permissions = []
        for codename, name, description in default_permissions:
            permission, _ = ConferencePermission.objects.get_or_create(
                codename=codename,
                defaults={'name': name, 'description': description}
            )
            permissions.append(permission)

        secretary_role = ConferenceRole.objects.create(
            conference=instance,
            role_type='secretary',
            name='Conference Secretary',
            description='Full administrative control over the conference'
        )
        secretary_role.permissions.set(permissions)

        deputy_permissions = [
            p for p in permissions if p.codename != 'delete_conference']
        deputy_role = ConferenceRole.objects.create(
            conference=instance,
            role_type='deputy',
            name='Conference Deputy',
            description='Administrative control with limited critical actions'
        )
        deputy_role.permissions.set(deputy_permissions)

        assistant_permissions = [p for p in permissions if p.codename in [
            'view_conference', 'add_people', 'edit_people', 'approve_people',
            'create_tasks', 'assign_tasks', 'edit_tasks', 'manage_categories'
        ]]
        assistant_role = ConferenceRole.objects.create(
            conference=instance,
            role_type='assistant',
            name='Conference Assistant',
            description='Handles routine administrative tasks'
        )
        assistant_role.permissions.set(assistant_permissions)

        if instance.created_by:
            ConferenceMember.objects.create(
                user=instance.created_by,
                conference=instance,
                role=secretary_role
            )
