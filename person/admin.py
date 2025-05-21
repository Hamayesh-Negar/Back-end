from django.contrib import admin
from django.forms import TimeInput, ModelForm, ModelMultipleChoiceField, CheckboxSelectMultiple
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from import_export import resources
from import_export.admin import ImportExportModelAdmin

from .models import Person, Category, Task, PersonTask


# Resources for import/export
class PersonResource(resources.ModelResource):
    class Meta:
        model = Person
        fields = ('id', 'first_name', 'last_name', 'email', 'telephone',
                  'conference__name', 'is_active')
        export_order = fields


class TaskResource(resources.ModelResource):
    class Meta:
        model = Task
        fields = ('id', 'name', 'description', 'is_required', 'is_active',
                  'conference__name', 'due_date')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'conference', 'get_members_count', 'created_at')
    list_filter = ('conference', 'created_at')
    search_fields = ('name', 'description', 'conference__name')

    def get_members_count(self, obj):
        count = obj.members.count()
        url = reverse('admin:person_person_changelist') + \
            f'?categories__id={obj.id}'
        return format_html('<a href="{}">{} members</a>', url, count)

    get_members_count.short_description = 'Members'


class PersonTaskInline(admin.TabularInline):
    model = PersonTask
    extra = 1
    fields = ('task', 'status', 'notes', 'completed_at', 'completed_by')
    readonly_fields = ('completed_at', 'completed_by')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('task', 'completed_by')


class PersonAdminForm(ModelForm):
    tasks = ModelMultipleChoiceField(
        queryset=Task.objects.all(),
        widget=CheckboxSelectMultiple,
        required=False,
        help_text="Select tasks to assign to this person"
    )

    class Meta:
        model = Person
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super(PersonAdminForm, self).__init__(*args, **kwargs)
        if self.instance.pk and hasattr(self.fields, 'tasks'):
            # For existing persons, show currently assigned tasks
            self.fields['tasks'].initial = Task.objects.filter(
                assignments__person=self.instance
            )
        elif 'conference' in self.data and hasattr(self.fields, 'tasks'):
            # Filter tasks by the selected conference
            conference_id = self.data.get('conference')
            if conference_id:
                self.fields['tasks'].queryset = Task.objects.filter(
                    conference_id=conference_id,
                    is_active=True
                )


@admin.register(Person)
class PersonAdmin(ImportExportModelAdmin):
    form = PersonAdminForm
    list_display = (
        'full_name',
        'conference_link',
        'unique_code',
        'email',
        'telephone',
        'get_categories',
        'get_tasks_progress',
        'is_active'
    )
    list_filter = ('is_active', 'conference', 'categories', 'created_at')
    search_fields = ('first_name', 'last_name', 'email',
                     'telephone', 'unique_code')
    readonly_fields = ('hashed_unique_code', 'registered_by',
                       'created_at', 'updated_at')
    inlines = [PersonTaskInline]

    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    full_name.short_description = 'Name'

    def conference_link(self, obj):
        url = reverse('admin:conference_conference_change',
                      args=[obj.conference.id])
        return mark_safe(f'<a href="{url}">{obj.conference.name}</a>')

    conference_link.short_description = 'Conference'

    def get_categories(self, obj):
        return mark_safe(
            ' '.join(
                f'<span class="badge badge-info">{category.name}</span>'
                for category in obj.categories.all()
            )
        )

    get_categories.short_description = 'Categories'

    def get_tasks_progress(self, obj):
        total = obj.tasks.count()
        if not total:
            return mark_safe('<span class="badge badge-secondary">No tasks</span>')

        completed = obj.tasks.filter(status='completed').count()
        percentage = (completed / total) * 100

        if percentage == 100:
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
                    {completed}/{total} ({int(percentage)}%)
                </div>
            </div>
            '''
        )

    get_tasks_progress.short_description = 'Tasks Progress'

    def save_model(self, request, obj, form, change):
        if not change:
            obj.registered_by = request.user
        obj.save()

        # Handle task assignments
        if 'tasks' in form.cleaned_data:
            selected_tasks = form.cleaned_data['tasks']

            # Create PersonTask objects for newly selected tasks
            for task in selected_tasks:
                PersonTask.objects.get_or_create(
                    person=obj,
                    task=task,
                    defaults={'status': PersonTask.PENDING}
                )

            # Optionally remove tasks that were deselected (only for existing persons)
            if change:
                obj.tasks.exclude(task__in=selected_tasks).delete()

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for obj in instances:
            if isinstance(obj, PersonTask):
                if obj.status == 'completed' and not obj.completed_by:
                    obj.completed_by = request.user
            obj.save()
        formset.save_m2m()

    class Media:
        css = {
            'all': ('css/custom_admin.css',)
        }
        js = ('js/person_admin.js',)


@admin.register(Task)
class TaskAdmin(ImportExportModelAdmin):
    resource_class = TaskResource

    list_display = (
        'name',
        'conference',
        'started_time',
        'finished_time',
        'is_required',
        'get_completion_stats',
        'get_total_completion_stats',
        'is_active'
    )
    list_filter = (
        'is_active',
        'is_required',
        'conference',
        'started_time',
        'finished_time',
    )
    search_fields = ('name', 'description', 'conference__name')

    formfield_overrides = {
        Task._meta.get_field('started_time'): {'widget': TimeInput(attrs={'type': 'datetime-local'})},
        Task._meta.get_field('finished_time'): {'widget': TimeInput(attrs={'type': 'datetime-local'})},
    }

    def get_completion_stats(self, obj):
        total = obj.assignments.count()
        if not total:
            return mark_safe('<span class="badge badge-secondary">Not assigned</span>')

        completed = obj.assignments.filter(status='completed').count()
        percentage = (completed / total) * 100

        if percentage == 100:
            color = 'success'
        elif percentage >= 50:
            color = 'warning'
        else:
            color = 'danger'

        return mark_safe(
            f'''
            <div class="progress" style="width: 100px;">
                <div class="progress-bar bg-{color}" role="progressbar" 
                     style="width: {percentage}%;">
                    {completed}/{total} ({int(percentage)}%)
                </div>
            </div>
            '''
        )

    get_completion_stats.short_description = 'Completion'

    def get_total_completion_stats(self, obj):
        # Get the total assignments and completed assignments for this specific task
        from .models import PersonTask

        total_assignments = obj.assignments.count()

        completed_assignments = obj.assignments.filter(
            status=PersonTask.COMPLETED
        ).count()

        if not total_assignments:
            return mark_safe('<span class="badge badge-secondary">Not assigned</span>')

        percentage = (completed_assignments / total_assignments) * 100

        if percentage == 100:
            color = 'success'
        elif percentage >= 50:
            color = 'warning'
        else:
            color = 'danger'

        return mark_safe(
            f'''
            <span class="badge badge-{color}">
                {completed_assignments}/{total_assignments} ({int(percentage)}%)
            </span>
            '''
        )

    get_total_completion_stats.short_description = 'Task Completion'


@admin.register(PersonTask)
class PersonTaskAdmin(admin.ModelAdmin):
    list_display = (
        'person',
        'task',
        'get_status_badge',
        'completed_at',
        'completed_by'
    )
    list_filter = (
        'status',
        'completed_at',
        'task__conference'
    )
    search_fields = (
        'person__first_name',
        'person__last_name',
        'task__name'
    )
    readonly_fields = ('completed_at', 'completed_by')
    raw_id_fields = ('person', 'task')
    date_hierarchy = 'completed_at'

    def get_status_badge(self, obj):
        colors = {
            'pending': 'secondary',
            'in_progress': 'info',
            'completed': 'success',
            'cancelled': 'danger'
        }
        return mark_safe(
            f'<span class="badge badge-{colors.get(obj.status, "secondary")}">'
            f'{obj.get_status_display()}</span>'
        )

    get_status_badge.short_description = 'Status'

    def save_model(self, request, obj, form, change):
        if obj.status == 'completed' and not obj.completed_by:
            obj.completed_by = request.user
        obj.save()

    class Media:
        css = {
            'all': ('css/custom_admin.css',)
        }
