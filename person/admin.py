from django.contrib import admin
from django.forms import TimeInput, ModelForm, ModelMultipleChoiceField, CheckboxSelectMultiple
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils import timezone
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


# Category Admin Form with filtered tasks
class CategoryAdminForm(ModelForm):
    """Custom form to filter tasks by conference"""

    class Meta:
        model = Category
        fields = '__all__'
        widgets = {
            'tasks': CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Filter tasks based on the selected conference
        if self.instance.pk:
            # For existing categories, filter by the category's conference
            self.fields['tasks'].queryset = Task.objects.filter(
                conference=self.instance.conference,
                is_active=True
            ).order_by('name')
        elif 'conference' in self.data:
            # For new categories with conference already selected
            conference_id = self.data.get('conference')
            if conference_id:
                self.fields['tasks'].queryset = Task.objects.filter(
                    conference_id=conference_id,
                    is_active=True
                ).order_by('name')
        else:
            # Show all tasks if conference not yet selected
            self.fields['tasks'].queryset = Task.objects.filter(
                is_active=True
            ).order_by('conference__name', 'name')

        # Add help text
        self.fields['tasks'].help_text = (
            "Select tasks that will be automatically assigned to all members of this category. "
            "Only tasks from the same conference are shown."
        )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    form = CategoryAdminForm
    list_display = ('name', 'conference', 'get_tasks_count',
                    'get_members_count', 'created_at')
    list_filter = ('conference', 'created_at')
    search_fields = ('name', 'description', 'conference__name')
    # Use horizontal filter widget for better UX
    filter_horizontal = ('tasks',)
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Basic Information', {
            'fields': ('conference', 'name', 'description')
        }),
        ('Auto-Assigned Tasks', {
            'fields': ('tasks',),
            'description': (
                'Tasks selected here will be automatically assigned to all current and future '
                'members of this category. Only tasks from the same conference can be selected.'
            ),
            'classes': ('wide',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_members_count(self, obj):
        count = obj.members.count()
        if count == 0:
            return mark_safe('<span class="badge badge-secondary">0 members</span>')

        url = reverse('admin:person_person_changelist') + \
            f'?categories__id={obj.id}'
        return format_html(
            '<a href="{}" class="badge badge-primary">{} members</a>',
            url,
            count
        )

    get_members_count.short_description = 'Members'

    def get_tasks_count(self, obj):
        count = obj.tasks.count()
        if count == 0:
            return mark_safe('<span class="badge badge-secondary">No tasks</span>')

        task_names = ', '.join([task.name for task in obj.tasks.all()[:3]])
        if count > 3:
            task_names += f', +{count - 3} more'

        return format_html(
            '<span class="badge badge-info" title="{}">{} tasks</span>',
            task_names,
            count
        )

    get_tasks_count.short_description = 'Auto-Assigned Tasks'

    def save_model(self, request, obj, form, change):
        """Save the category and auto-assign tasks to existing members"""
        is_new = not change
        super().save_model(request, obj, form, change)

        # If this is an update and tasks were modified, assign tasks to all members
        if change and 'tasks' in form.changed_data:
            members_count = 0
            for person in obj.members.all():
                obj.assign_tasks_to_person(person)
                members_count += 1

            if members_count > 0:
                self.message_user(
                    request,
                    f'Tasks updated and auto-assigned to {members_count} existing members.',
                    level='SUCCESS'
                )

    actions = ['assign_tasks_to_all_members']

    def assign_tasks_to_all_members(self, request, queryset):
        """Assign category tasks to all members of selected categories"""
        total_assignments = 0
        total_members = 0

        for category in queryset:
            members = category.members.all()
            for person in members:
                for task in category.tasks.all():
                    _, created = PersonTask.objects.get_or_create(
                        person=person,
                        task=task,
                        defaults={'status': PersonTask.PENDING}
                    )
                    if created:
                        total_assignments += 1
            total_members += members.count()

        self.message_user(
            request,
            f'Successfully assigned tasks to {total_members} members across {queryset.count()} categories. '
            f'{total_assignments} new task assignments created.',
            level='SUCCESS'
        )

    assign_tasks_to_all_members.short_description = 'Assign category tasks to all members'

    class Media:
        css = {
            'all': ('css/custom_admin.css',)
        }
        js = ('admin/js/jquery.init.js', 'js/category_admin.js',)


class PersonTaskInline(admin.TabularInline):
    model = PersonTask
    extra = 1
    fields = ('task', 'status', 'get_source',
              'notes', 'completed_at', 'completed_by')
    readonly_fields = ('completed_at', 'completed_by', 'get_source')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('task', 'completed_by')

    def get_source(self, obj):
        """Show if this task was auto-assigned from a category"""
        if not obj.person_id or not obj.task_id:
            return '-'

        # Check if this task is in any of the person's categories
        person_categories = obj.person.categories.all()
        category_tasks = []

        for category in person_categories:
            if obj.task in category.tasks.all():
                category_tasks.append(category.name)

        if category_tasks:
            return mark_safe(
                f'<span class="badge badge-success" title="Auto-assigned from category">'
                f'From: {", ".join(category_tasks)}</span>'
            )
        return mark_safe('<span class="badge badge-secondary">Manual</span>')

    get_source.short_description = 'Source'


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

        # Filter categories by conference
        if self.instance.pk:
            # For existing persons, filter categories by person's conference
            self.fields['categories'].queryset = Category.objects.filter(
                conference=self.instance.conference
            ).order_by('name')

            # Show currently assigned tasks
            if hasattr(self.fields, 'tasks'):
                self.fields['tasks'].initial = Task.objects.filter(
                    assignments__person=self.instance
                )
                # Filter tasks by person's conference
                self.fields['tasks'].queryset = Task.objects.filter(
                    conference=self.instance.conference,
                    is_active=True
                ).order_by('name')
        elif 'conference' in self.data:
            # For new persons with conference already selected
            conference_id = self.data.get('conference')
            if conference_id:
                # Filter categories by selected conference
                self.fields['categories'].queryset = Category.objects.filter(
                    conference_id=conference_id
                ).order_by('name')

                # Filter tasks by the selected conference
                if hasattr(self.fields, 'tasks'):
                    self.fields['tasks'].queryset = Task.objects.filter(
                        conference_id=conference_id,
                        is_active=True
                    ).order_by('name')
        else:
            # Show all categories and tasks if conference not yet selected
            self.fields['categories'].queryset = Category.objects.all().order_by(
                'conference__name', 'name')
            if hasattr(self.fields, 'tasks'):
                self.fields['tasks'].queryset = Task.objects.filter(
                    is_active=True
                ).order_by('conference__name', 'name')


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
        categories = obj.categories.all()
        if not categories:
            return mark_safe('<span class="badge badge-secondary">No categories</span>')

        badges = []
        for category in categories:
            task_count = category.tasks.count()
            title = f"{category.name}"
            if task_count > 0:
                title += f" ({task_count} auto-assigned tasks)"

            badges.append(
                f'<span class="badge badge-info" title="{title}">{category.name}</span>'
            )

        return mark_safe(' '.join(badges))

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

    actions = ['reassign_category_tasks']

    def reassign_category_tasks(self, request, queryset):
        """Re-assign all category tasks to selected persons"""
        count = 0
        tasks_count = 0

        for person in queryset:
            for category in person.categories.all():
                for task in category.tasks.all():
                    _, created = PersonTask.objects.get_or_create(
                        person=person,
                        task=task,
                        defaults={'status': PersonTask.PENDING}
                    )
                    if created:
                        tasks_count += 1
                count += 1

        self.message_user(
            request,
            f'Successfully re-assigned category tasks to {count} persons. {tasks_count} new task assignments created.',
            level='SUCCESS'
        )

    reassign_category_tasks.short_description = 'Re-assign category tasks to selected persons'

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
            if not obj.completed_at:
                obj.completed_at = timezone.now()
        obj.save()

    class Media:
        css = {
            'all': ('css/custom_admin.css',)
        }
