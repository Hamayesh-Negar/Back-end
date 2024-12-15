from django.contrib import admin
from django.utils.html import mark_safe
from django.urls import reverse
from django.utils import timezone
from django.db.models import Count, Q
from import_export.admin import ImportExportModelAdmin
from import_export import resources
from .models import Conference


class ConferenceResource(resources.ModelResource):
    class Meta:
        model = Conference
        fields = ('id', 'name', 'description', 'start_date', 'end_date', 'is_active')
        export_order = fields


@admin.register(Conference)
class ConferenceAdmin(ImportExportModelAdmin):
    resource_class = ConferenceResource

    list_display = (
        'name',
        'date_range',
        'get_status',
        'get_attendees_count',
        'get_tasks_count',
        'get_completion_rate',
        'is_active'
    )
    list_filter = (
        'is_active',
        'start_date',
        'end_date'
    )
    search_fields = ('name', 'description')
    date_hierarchy = 'start_date'

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
            return mark_safe(f'<span class="badge badge-info">Starts in {days} days</span>')
        elif today > obj.end_date:
            return mark_safe('<span class="badge badge-secondary">Ended</span>')
        else:
            days_left = (obj.end_date - today).days
            return mark_safe(f'<span class="badge badge-success">{days_left} days remaining</span>')

    get_status.short_description = 'Status'

    def get_attendees_count(self, obj):
        count = obj.attendees.count()
        url = reverse('admin:person_person_changelist') + f'?conference__id={obj.id}'
        return mark_safe(f'<a href="{url}">{count} attendees</a>')

    get_attendees_count.short_description = 'Attendees'

    def get_tasks_count(self, obj):
        count = obj.tasks.count()
        url = reverse('admin:person_task_changelist') + f'?conference__id={obj.id}'
        return mark_safe(f'<a href="{url}">{count} tasks</a>')

    get_tasks_count.short_description = 'Tasks'

    def get_completion_rate(self, obj):
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
            color = 'success'
        elif percentage >= 50:
            color = 'warning'
        else:
            color = 'danger'

        return mark_safe(
            f'''
            <div class="progress" style="width: 100px;">
                <div class="progress-bar bg-{color}" role="progressbar" 
                     style="width: {percentage}%;" aria-valuenow="{percentage}" 
                     aria-valuemin="0" aria-valuemax="100">
                    {percentage:.1f}%
                </div>
            </div>
            '''
        )

    get_completion_rate.short_description = 'Completion Rate'

    class Media:
        css = {
            'all': ('css/custom_admin.css',)
        }
