from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html, mark_safe
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.db.models import Count

from .models import User, UserPreference


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'phone', 'full_name', 'get_conference_memberships',
                    'is_verified', 'is_active', 'is_staff', 'date_joined')
    list_filter = ('is_active', 'is_staff', 'is_verified', 'date_joined')
    search_fields = ('username', 'email', 'phone', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    filter_horizontal = ('groups', 'user_permissions',)
    readonly_fields = ('date_joined', 'get_conference_memberships',
                       'get_conference_roles', 'get_invitations_summary')

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {
         'fields': ('first_name', 'last_name', 'email', 'phone')}),
        (_('Permissions'), {
            'fields': ('is_active', 'is_verified', 'is_staff', 'is_superuser',
                       'groups', 'user_permissions'),
        }),
        (_('Conference Information'), {
            'fields': ('get_conference_memberships', 'get_conference_roles', 'get_invitations_summary'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'phone', 'password1', 'password2'),
        }),
    )

    def full_name(self, obj):
        return obj.get_full_name() or obj.username

    full_name.short_description = _('Full Name')

    def get_conference_memberships(self, obj):
        if not obj.pk:
            return "No memberships yet"

        memberships = obj.conference_memberships.select_related(
            'conference', 'role').filter(status='active')
        count = memberships.count()

        if count == 0:
            return "No active memberships"

        url = reverse(
            'admin:conference_conferencemember_changelist') + f'?user__id={obj.id}'
        return mark_safe(f'<a href="{url}">{count} active memberships</a>')

    get_conference_memberships.short_description = 'Conference Memberships'

    def get_conference_roles(self, obj):
        if not obj.pk:
            return "No roles yet"

        memberships = obj.conference_memberships.select_related(
            'conference', 'role').filter(status='active')

        if not memberships.exists():
            return "No active roles"

        role_info = []
        for membership in memberships[:3]:
            colors = {
                'secretary': '#dc3545',
                'deputy': '#fd7e14',
                'assistant': '#28a745'
            }
            color = colors.get(membership.role.role_type, '#6c757d')
            role_info.append(
                f'<span style="background: {color}; color: white; padding: 1px 6px; border-radius: 2px; font-size: 10px;">'
                f'{membership.role.get_role_type_display()}</span> in {membership.conference.name}'
            )

        if memberships.count() > 3:
            role_info.append(f"... and {memberships.count() - 3} more")

        return mark_safe('<br>'.join(role_info))

    get_conference_roles.short_description = 'Conference Roles'

    def get_invitations_summary(self, obj):
        if not obj.pk:
            return "No invitations yet"

        received_pending = obj.conference_invitations.filter(
            status='pending').count()
        received_total = obj.conference_invitations.count()

        sent_pending = obj.sent_invitations.filter(status='pending').count()
        sent_total = obj.sent_invitations.count()

        summary = []
        if received_total > 0:
            url = reverse(
                'admin:conference_conferenceinvitation_changelist') + f'?invited_user__id={obj.id}'
            summary.append(
                f'<a href="{url}">Received: {received_total} ({received_pending} pending)</a>')

        if sent_total > 0:
            url = reverse(
                'admin:conference_conferenceinvitation_changelist') + f'?invited_by__id={obj.id}'
            summary.append(
                f'<a href="{url}">Sent: {sent_total} ({sent_pending} pending)</a>')

        if not summary:
            return "No invitations"

        return mark_safe('<br>'.join(summary))

    get_invitations_summary.short_description = 'Invitations'

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('conference_memberships__conference', 'conference_memberships__role')

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        is_superuser = request.user.is_superuser

        if not is_superuser:
            if 'is_superuser' in form.base_fields:
                form.base_fields['is_superuser'].disabled = True
            if 'is_staff' in form.base_fields:
                form.base_fields['is_staff'].disabled = True
            if 'user_permissions' in form.base_fields:
                form.base_fields['user_permissions'].disabled = True
            if 'groups' in form.base_fields:
                form.base_fields['groups'].disabled = True

        return form

    def has_delete_permission(self, request, obj=None):
        if not request.user.is_superuser:
            return False
        return super().has_delete_permission(request, obj)

    class Media:
        css = {
            'all': ('css/custom_admin.css',)
        }


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'selected_conference', 'updated_at')
    list_filter = ('updated_at', 'created_at')
    search_fields = ('user__username', 'user__email',
                     'selected_conference__name')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('user', 'selected_conference')

    fieldsets = (
        (_('User Information'), {
            'fields': ('user',)
        }),
        (_('Preferences'), {
            'fields': ('selected_conference',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'selected_conference')
