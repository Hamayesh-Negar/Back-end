import hashlib
import uuid

from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone

from conference.models import Conference


class Category(models.Model):
    conference = models.ForeignKey(Conference, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=75)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "categories"
        unique_together = ['conference', 'name']
        ordering = ['name']

    def __str__(self):
        return f"{self.name} - {self.conference.name}"


class Person(models.Model):
    conference = models.ForeignKey(Conference, on_delete=models.CASCADE, related_name='attendees')
    categories = models.ManyToManyField('Category', related_name='members')
    unique_code = models.CharField(
        max_length=255,
        unique=True,
        blank=True,
        help_text="Enter a unique code or leave blank for auto-generation"
    )
    hashed_unique_code = models.TextField(
        editable=False,
        help_text="Hashed version of the unique code"
    )

    first_name = models.CharField(max_length=64)
    last_name = models.CharField(max_length=64)
    telephone = models.CharField(max_length=24, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    registered_by = models.ForeignKey('user.User', on_delete=models.SET_NULL, null=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "people"
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.conference.name}"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    def generate_unique_code(self):
        base_uuid = str(uuid.uuid4())
        return f"{self.conference.id}-{self.first_name}-{self.last_name}-{base_uuid}"

    @staticmethod
    def hash_unique_code(code):
        return hashlib.sha256(str(code).encode()).hexdigest()

    def save(self, *args, **kwargs):
        if not self.unique_code:
            self.unique_code = self.generate_unique_code()

        self.hashed_unique_code = self.hash_unique_code(self.unique_code)

        if not self.pk and not self.registered_by and hasattr(kwargs, 'request'):
            self.registered_by = kwargs.pop('request').user

        super().save(*args, **kwargs)


@receiver(pre_save, sender=Person)
def ensure_hashed_code(sender, instance, **kwargs):
    if instance.unique_code and not instance.hashed_unique_code:
        instance.hashed_unique_code = instance.hash_unique_code(instance.unique_code)


class Task(models.Model):
    conference = models.ForeignKey(Conference, on_delete=models.CASCADE, related_name='tasks')
    name = models.CharField(max_length=64)
    description = models.TextField(null=True, blank=True)
    is_required = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    started_time = models.DateTimeField(null=True, blank=True)
    finished_time = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['due_date', 'name']
        unique_together = ['conference', 'name']

    def __str__(self):
        return f"{self.name} - {self.conference.name}"


class PersonTask(models.Model):
    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (IN_PROGRESS, 'In Progress'),
        (COMPLETED, 'Completed'),
        (CANCELLED, 'Cancelled'),
    ]

    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='tasks')
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='assignments')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    notes = models.TextField(blank=True, null=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey('user.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "person tasks"
        unique_together = ['person', 'task']
        ordering = ['task__due_date', 'created_at']

    def __str__(self):
        return f"{self.person.get_full_name()} - {self.task.name}"

    def mark_completed(self, user):
        self.status = self.COMPLETED
        self.completed_at = timezone.now()
        self.completed_by = user
        self.save()
