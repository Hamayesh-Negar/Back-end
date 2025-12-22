"""
Async utilities for database operations using asgiref.

These utilities wrap synchronous Django ORM calls to work with async views.
"""

from asgiref.sync import sync_to_async
from django.db.models import QuerySet
from django.utils import timezone
from person.models import Person, Category, PersonTask, Task


@sync_to_async
def get_user_conference(user):
    if hasattr(user, 'preference') and user.preference.selected_conference:
        return user.preference.selected_conference
    return None


@sync_to_async
def get_person_by_hashed_code(hashed_unique_code):
    try:
        return Person.objects.get(hashed_unique_code=hashed_unique_code)
    except Person.DoesNotExist:
        return None


@sync_to_async
def get_person_tasks_count(person):
    tasks = person.tasks.all()
    return {
        'total': tasks.count(),
        'completed': tasks.filter(status=PersonTask.COMPLETED).count(),
        'pending': tasks.filter(status=PersonTask.PENDING).count(),
    }


@sync_to_async
def get_task_by_id(task_id):
    try:
        return Task.objects.get(id=task_id)
    except Task.DoesNotExist:
        return None


@sync_to_async
def get_person_task(person, task):
    try:
        return PersonTask.objects.get(person=person, task=task)
    except PersonTask.DoesNotExist:
        return None


@sync_to_async
def mark_person_task_completed(person_task, user):
    person_task.status = PersonTask.COMPLETED
    person_task.completed_at = timezone.now()
    person_task.completed_by = user
    person_task.save()
    return person_task


@sync_to_async
def assign_categories_to_person(person, category_ids):
    if category_ids is not None:
        person.categories.set(category_ids)
    return person


@sync_to_async
def assign_tasks_to_person(person, task_ids):
    if task_ids:
        for task_id in task_ids:
            PersonTask.objects.get_or_create(
                person=person,
                task_id=task_id,
                defaults={'status': PersonTask.PENDING}
            )
    return person


@sync_to_async
def get_task_completion_stats(task):
    total = task.assignments.count()
    completed = task.assignments.filter(status=PersonTask.COMPLETED).count()
    pending = task.assignments.filter(status=PersonTask.PENDING).count()

    return {
        'total_assignments': total,
        'completed': completed,
        'pending': pending,
        'completion_rate': round((completed / total * 100), 2) if total > 0 else 0
    }


@sync_to_async
def reorder_tasks(orders, conference_id):
    updated_count = 0
    for item in orders:
        task_id = item.get('id')
        new_order = item.get('order')
        if task_id is not None and new_order is not None:
            updated_count += Task.objects.filter(
                id=task_id, conference_id=conference_id).update(order=new_order)
    return updated_count


@sync_to_async
def add_category_members(category, person_ids):
    persons = Person.objects.filter(
        id__in=person_ids,
        conference=category.conference
    )
    category.members.add(*persons)
    return category


@sync_to_async
def get_category_members(category):
    return list(category.members.all())


@sync_to_async
def bulk_assign_tasks(task, person_ids):
    existing_assignments = set(
        task.assignments.values_list('person_id', flat=True)
    )
    new_assignments = set(person_ids) - existing_assignments

    bulk_assignments = [
        PersonTask(
            task=task,
            person_id=person_id,
            status=PersonTask.PENDING
        ) for person_id in new_assignments if isinstance(person_id, int)
    ]

    if bulk_assignments:
        PersonTask.objects.bulk_create(bulk_assignments)

    return len(bulk_assignments)


@sync_to_async
def bulk_unassign_tasks(task, person_ids):
    valid_person_ids = [pid for pid in person_ids if isinstance(pid, int)]

    deleted_count, _ = PersonTask.objects.filter(
        task=task,
        person_id__in=valid_person_ids
    ).delete()

    return deleted_count


@sync_to_async
def bulk_create_persons(persons_data_list, user):
    persons = []
    for person_data in persons_data_list:
        person = Person(
            conference=person_data['conference'],
            first_name=person_data['first_name'],
            last_name=person_data['last_name'],
            email=person_data.get('email'),
            telephone=person_data.get('telephone'),
            gender=person_data.get('gender', 'male'),
            unique_code=person_data.get('unique_code', ''),
            registered_by=user
        )
        persons.append(person)

    created_persons = Person.objects.bulk_create(persons)
    return created_persons
