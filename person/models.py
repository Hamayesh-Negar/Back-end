from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=64)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Person(models.Model):
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

    def __str__(self):
        return f"{self.person} - {self.category}"
