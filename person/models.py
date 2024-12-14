from django.db import models
from django.utils import timezone

from conference.models import Conference


class Category(models.Model):
    name = models.CharField(max_length=75)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Person(models.Model):
    conference = models.ForeignKey(Conference, on_delete=models.CASCADE)
    unique_code = models.CharField(max_length=255, unique=True)
    hashed_unique_code = models.TextField()
    first_name = models.CharField(max_length=64)
    last_name = models.CharField(max_length=64)
    telephone = models.CharField(max_length=24)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    categories = models.ManyToManyField(Category, through='PersonCategory')

    class Meta:
        verbose_name_plural = "person"

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class PersonCategory(models.Model):
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)

    class Meta:
        verbose_name_plural = "person categories"
        unique_together = ['person', 'category']


class Task(models.Model):
    name = models.CharField(max_length=64)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.name} - {self.description}'


class TaskStatus(models.Model):
    is_done = models.BooleanField(default=False)
    done_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "task statuses"

    def mark_as_done(self):
        self.is_done = True
        self.done_at = timezone.now()
        self.save()


class TaskPerson(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    task_status = models.ForeignKey(TaskStatus, on_delete=models.CASCADE)

    class Meta:
        verbose_name_plural = "task assignments"
        unique_together = ['task', 'person']
