from django.contrib import admin
from django.utils.html import mark_safe
from django.urls import reverse
from django.utils import timezone
from django.db.models import Count, Q
from django.core.exceptions import ValidationError
from django.forms import ModelForm
from import_export.admin import ImportExportModelAdmin
from import_export import resources
from .models import Conference, ConferenceRole, ConferencePermission, ConferenceMember, ConferenceInvitation


class ConferenceResource(resources.ModelResource):
    class Meta:
        model = Conference
        fields = ('id', 'name', 'slug', 'description', 'start_date', 'end_date', 'is_active',
                  'max_executives', 'max_members', 'enable_categorization',
                  'max_tasks_per_conference', 'max_tasks_per_user')
        export_order = fields


class ConferenceMemberInline(admin.TabularInline):
    """Inline admin for conference members"""
    model = ConferenceMember
    extra = 0
    fields = ('user', 'role', 'status', 'joined_at')
    readonly_fields = ('joined_at',)
    autocomplete_fields = ('user',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'role')


class ConferenceRoleInline(admin.TabularInline):
    """Inline admin for conference roles"""
    model = ConferenceRole
    extra = 0
    fields = ('role_type', 'name', 'description', 'is_active')
    readonly_fields = ('created_at', 'updated_at')


class ConferenceInvitationInline(admin.TabularInline):
    """Inline admin for conference invitations"""
    model = ConferenceInvitation
    extra = 0
    fields = ('invited_user', 'invited_by', 'role',
              'status', 'expires_at', 'created_at')
    readonly_fields = ('created_at', 'responded_at')
    autocomplete_fields = ('invited_user', 'invited_by')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('invited_user', 'invited_by', 'role')


@admin.register(Conference)
class ConferenceAdmin(ImportExportModelAdmin):
    resource_class = ConferenceResource
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ConferenceRoleInline,
               ConferenceMemberInline, ConferenceInvitationInline]

    list_display = (
        'name',
        'date_range',
        'get_status',
        'get_members_info',
        'get_executives_info',
        'get_attendees_count',
        'get_tasks_count',
        'get_completion_rate',
        'is_active'
    )
    list_filter = (
        'is_active',
        'start_date',
        'end_date',
        'enable_categorization',
        'created_at'
    )
    search_fields = ('name', 'slug', 'description', 'created_by__username')
    date_hierarchy = 'start_date'
    readonly_fields = ('created_at', 'updated_at',
                       'created_by', 'get_configuration_summary')

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'description', 'created_by')
        }),
        ('Schedule', {
            'fields': ('start_date', 'end_date', 'is_active')
        }),
        ('Configuration', {
            'fields': ('max_executives', 'max_members', 'enable_categorization',
                       'max_tasks_per_conference', 'max_tasks_per_user'),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': ('get_configuration_summary', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def get_configuration_summary(self, obj):
        """Display configuration summary"""
        if not obj.pk:
            return "Configuration will be shown after saving"

        current_members = obj.members.filter(status='active').count()
        current_executives = obj.members.filter(
            role__role_type__in=['secretary', 'deputy', 'assistant'],
            status='active'
        ).count()

        return mark_safe(f"""
        <div style="line-height: 1.6;">
            <strong>Members:</strong> {current_members}/{obj.max_members}<br>
            <strong>Executives:</strong> {current_executives}/{obj.max_executives}<br>
            <strong>Categorization:</strong> {'Enabled' if obj.enable_categorization else 'Disabled'}<br>
            <strong>Task Limits:</strong> {obj.max_tasks_per_conference} per conference, {obj.max_tasks_per_user} per user
        </div>
        """)

    get_configuration_summary.short_description = 'Configuration Summary'

    def date_range(self, obj):
        return mark_safe(
            f'<span style="white-space:nowrap;">{obj.start_date.strftime("%Y-%m-%d")}</span> - '
            f'<span style="white-space:nowrap;">{obj.end_date.strftime("%Y-%m-%d")}</span>'
        )

    date_range.short_description = 'Duration'

    def get_status(self, obj):
        today = timezone.now().date()
        if today < obj.start_date:
            days = (obj.start_date - today).days
            return mark_safe(f'<span style="background: #17a2b8; color: white; padding: 2px 8px; border-radius: 3px;">Starts in {days} days</span>')
        elif today > obj.end_date:
            return mark_safe('<span style="background: #6c757d; color: white; padding: 2px 8px; border-radius: 3px;">Ended</span>')
        else:
            days_left = (obj.end_date - today).days
            return mark_safe(f'<span style="background: #28a745; color: white; padding: 2px 8px; border-radius: 3px;">{days_left} days remaining</span>')

    get_status.short_description = 'Status'

    def get_members_info(self, obj):
        """Display member count with breakdown"""
        total_members = obj.members.filter(status='active').count()
        url = reverse('admin:conference_conferencemember_changelist') + \
            f'?conference__id={obj.id}'

        color = '#28a745' if total_members < obj.max_members * \
            0.8 else '#ffc107' if total_members < obj.max_members else '#dc3545'

        return mark_safe(f'<a href="{url}" style="color: {color}; font-weight: bold;">{total_members}/{obj.max_members}</a>')

    get_members_info.short_description = 'Members'

    def get_executives_info(self, obj):
        """Display executive count"""
        executives = obj.members.filter(
            role__role_type__in=['secretary', 'deputy', 'assistant'],
            status='active'
        ).count()

        url = reverse('admin:conference_conferencemember_changelist') + \
            f'?conference__id={obj.id}&role__role_type__in=secretary,deputy,assistant'
        color = '#28a745' if executives < obj.max_executives * \
            0.8 else '#ffc107' if executives < obj.max_executives else '#dc3545'

        return mark_safe(f'<a href="{url}" style="color: {color}; font-weight: bold;">{executives}/{obj.max_executives}</a>')

    get_executives_info.short_description = 'Executives'

    def get_attendees_count(self, obj):
        count = obj.attendees.count()
        url = reverse('admin:person_person_changelist') + \
            f'?conference__id={obj.id}'
        return mark_safe(f'<a href="{url}">{count} attendees</a>')

    get_attendees_count.short_description = 'Attendees'

    def get_tasks_count(self, obj):
        # This might need adjustment based on your task model structure
        try:
            count = obj.tasks.count()
            url = reverse('admin:person_task_changelist') + \
                f'?conference__id={obj.id}'
            return mark_safe(f'<a href="{url}">{count} tasks</a>')
        except:
            return "N/A"

    get_tasks_count.short_description = 'Tasks'

    def get_completion_rate(self, obj):
        try:
            total_tasks = obj.tasks.aggregate(
                total_assignments=Count('assignments')
            )['total_assignments']

            if not total_tasks:
                return "No tasks assigned"

            completed_tasks = obj.tasks.aggregate(
                completed=Count('assignments',
                                filter=Q(assignments__status='completed'))
            )['completed']

            percentage = (completed_tasks / total_tasks) * 100

            if percentage >= 75:
                color = '#28a745'
            elif percentage >= 50:
                color = '#ffc107'
            else:
                color = '#dc3545'

            return mark_safe(
                f'''
                <div style="display: flex; align-items: center; gap: 5px;">
                    <div style="width: 60px; height: 8px; background: #e9ecef; border-radius: 4px; overflow: hidden;">
                        <div style="width: {percentage}%; height: 100%; background: {color};"></div>
                    </div>
                    <span style="font-size: 11px; color: {color}; font-weight: bold;">{percentage:.1f}%</span>
                </div>
                '''
            )
        except:
            return "N/A"

    get_completion_rate.short_description = 'Completion Rate'

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    class Media:
        css = {
            'all': ('css/custom_admin.css',)
        }


@admin.register(ConferencePermission)
class ConferencePermissionAdmin(admin.ModelAdmin):
    """Admin for conference permissions"""
    list_display = ('codename', 'name', 'description',
                    'get_roles_count', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('codename', 'name', 'description')
    readonly_fields = ('created_at', 'get_roles_count')

    fieldsets = (
        ('Permission Details', {
            'fields': ('codename', 'name', 'description')
        }),
        ('Statistics', {
            'fields': ('get_roles_count', 'created_at'),
            'classes': ('collapse',)
        })
    )

    def get_roles_count(self, obj):
        """Count how many roles have this permission"""
        if not obj.pk:
            return "N/A"
        count = obj.roles.count()
        url = reverse('admin:conference_conferencerole_changelist') + \
            f'?permissions__id={obj.id}'
        return mark_safe(f'<a href="{url}">{count} roles</a>')

    get_roles_count.short_description = 'Used by Roles'

    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of permissions that are in use
        if obj and obj.roles.exists():
            return False
        return super().has_delete_permission(request, obj)


class ConferenceRoleForm(ModelForm):
    """Custom form for ConferenceRole with validation"""
    class Meta:
        model = ConferenceRole
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        role_type = cleaned_data.get('role_type')
        conference = cleaned_data.get('conference')

        if role_type == 'secretary' and conference:
            # Check if secretary already exists for this conference
            existing_secretary = ConferenceRole.objects.filter(
                conference=conference,
                role_type='secretary'
            ).exclude(pk=self.instance.pk if self.instance else None)

            if existing_secretary.exists():
                raise ValidationError(
                    'Only one Secretary role is allowed per conference.')

        return cleaned_data


@admin.register(ConferenceRole)
class ConferenceRoleAdmin(admin.ModelAdmin):
    """Admin for conference roles"""
    form = ConferenceRoleForm
    list_display = ('name', 'conference', 'role_type', 'get_permissions_count',
                    'get_members_count', 'is_active', 'created_at')
    list_filter = ('role_type', 'is_active', 'created_at', 'conference')
    search_fields = ('name', 'description', 'conference__name')
    autocomplete_fields = ('conference',)
    filter_horizontal = ('permissions',)
    readonly_fields = ('created_at', 'updated_at', 'get_members_count')

    fieldsets = (
        ('Role Information', {
            'fields': ('conference', 'role_type', 'name', 'description', 'is_active')
        }),
        ('Permissions', {
            'fields': ('permissions',)
        }),
        ('Statistics', {
            'fields': ('get_members_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def get_permissions_count(self, obj):
        """Count permissions for this role"""
        count = obj.permissions.count()
        return f"{count} permissions"

    get_permissions_count.short_description = 'Permissions'

    def get_members_count(self, obj):
        """Count members with this role"""
        if not obj.pk:
            return "N/A"
        count = obj.members.filter(status='active').count()
        url = reverse(
            'admin:conference_conferencemember_changelist') + f'?role__id={obj.id}'
        return mark_safe(f'<a href="{url}">{count} members</a>')

    get_members_count.short_description = 'Active Members'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('conference').prefetch_related('permissions', 'members')


@admin.register(ConferenceMember)
class ConferenceMemberAdmin(admin.ModelAdmin):
    """Admin for conference members"""
    list_display = ('user', 'conference', 'get_role_info',
                    'status', 'get_permissions_summary', 'joined_at')
    list_filter = ('status', 'role__role_type', 'joined_at', 'conference')
    search_fields = ('user__username', 'user__first_name',
                     'user__last_name', 'conference__name', 'role__name')
    autocomplete_fields = ('user', 'conference', 'role')
    readonly_fields = ('joined_at', 'updated_at', 'get_permissions_summary')

    fieldsets = (
        ('Member Information', {
            'fields': ('user', 'conference', 'role', 'status')
        }),
        ('Details', {
            'fields': ('get_permissions_summary', 'joined_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def get_role_info(self, obj):
        """Display role type with styling"""
        colors = {
            'secretary': '#dc3545',
            'deputy': '#fd7e14',
            'assistant': '#28a745'
        }
        color = colors.get(obj.role.role_type, '#6c757d')
        return mark_safe(f'<span style="background: {color}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">{obj.role.get_role_type_display()}</span>')

    get_role_info.short_description = 'Role Type'

    def get_permissions_summary(self, obj):
        """Display permissions for this member"""
        if not obj.pk:
            return "Permissions will be shown after saving"

        permissions = obj.role.permissions.all()
        if not permissions:
            return "No permissions assigned"

        permission_list = [p.name for p in permissions[:5]]
        if len(permissions) > 5:
            permission_list.append(f"... and {len(permissions) - 5} more")

        return mark_safe("<br>".join(permission_list))

    get_permissions_summary.short_description = 'Permissions'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'conference', 'role').prefetch_related('role__permissions')

    def save_model(self, request, obj, form, change):
        try:
            obj.full_clean()
            super().save_model(request, obj, form, change)
        except ValidationError as e:
            form.add_error(None, e)


@admin.register(ConferenceInvitation)
class ConferenceInvitationAdmin(admin.ModelAdmin):
    """Admin for conference invitations"""
    list_display = ('invited_user', 'conference', 'get_role_info',
                    'status', 'get_status_info', 'invited_by', 'created_at')
    list_filter = ('status', 'role__role_type',
                   'created_at', 'expires_at', 'conference')
    search_fields = ('invited_user__username', 'invited_user__first_name', 'invited_user__last_name',
                     'conference__name', 'invited_by__username')
    autocomplete_fields = ('invited_user', 'invited_by', 'conference', 'role')
    readonly_fields = ('created_at', 'responded_at',
                       'get_status_info', 'get_time_remaining')

    fieldsets = (
        ('Invitation Details', {
            'fields': ('conference', 'invited_user', 'invited_by', 'role', 'message')
        }),
        ('Status Information', {
            'fields': ('status', 'get_status_info', 'expires_at', 'get_time_remaining', 'responded_at')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )

    def get_role_info(self, obj):
        """Display role type with styling"""
        colors = {
            'secretary': '#dc3545',
            'deputy': '#fd7e14',
            'assistant': '#28a745'
        }
        color = colors.get(obj.role.role_type, '#6c757d')
        return mark_safe(f'<span style="background: {color}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">{obj.role.get_role_type_display()}</span>')

    get_role_info.short_description = 'Role Type'

    def get_status_info(self, obj):
        """Display status with appropriate styling and information"""
        colors = {
            'pending': '#ffc107',
            'accepted': '#28a745',
            'rejected': '#dc3545',
            'expired': '#6c757d'
        }

        color = colors.get(obj.status, '#6c757d')
        status_display = obj.get_status_display()

        # Add extra info for pending invitations
        if obj.status == 'pending':
            now = timezone.now()
            if now > obj.expires_at:
                status_display += " (Expired)"
                color = colors['expired']
            else:
                time_left = obj.expires_at - now
                if time_left.days > 0:
                    status_display += f" ({time_left.days}d left)"
                elif time_left.seconds > 3600:
                    hours = time_left.seconds // 3600
                    status_display += f" ({hours}h left)"
                else:
                    status_display += " (Expiring soon)"

        return mark_safe(f'<span style="background: {color}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">{status_display}</span>')

    get_status_info.short_description = 'Status Info'

    def get_time_remaining(self, obj):
        """Show time remaining for pending invitations"""
        if obj.status != 'pending':
            return "N/A"

        now = timezone.now()
        if now > obj.expires_at:
            return mark_safe('<span style="color: #dc3545; font-weight: bold;">Expired</span>')

        time_left = obj.expires_at - now
        if time_left.days > 0:
            return f"{time_left.days} days remaining"
        elif time_left.seconds > 3600:
            hours = time_left.seconds // 3600
            return f"{hours} hours remaining"
        else:
            return mark_safe('<span style="color: #ffc107; font-weight: bold;">Expiring soon</span>')

    get_time_remaining.short_description = 'Time Remaining'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('invited_user', 'invited_by', 'conference', 'role')

    actions = ['mark_as_expired', 'extend_expiry']

    def mark_as_expired(self, request, queryset):
        """Mark pending invitations as expired"""
        updated = queryset.filter(status='pending').update(status='expired')
        self.message_user(request, f"{updated} invitations marked as expired.")

    mark_as_expired.short_description = "Mark selected invitations as expired"

    def extend_expiry(self, request, queryset):
        """Extend expiry by 7 days for pending invitations"""
        from datetime import timedelta
        updated_count = 0
        for invitation in queryset.filter(status='pending'):
            invitation.expires_at += timedelta(days=7)
            invitation.save()
            updated_count += 1

        self.message_user(
            request, f"Extended expiry for {updated_count} invitations by 7 days.")

    extend_expiry.short_description = "Extend expiry by 7 days"
