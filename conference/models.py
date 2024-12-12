from django.db import models


class Conference(models.Model):
    name = models.CharField(help_text='Conference name', max_length=255)
    description = models.TextField(help_text='Conference description', null=True, blank=True)
    start_date = models.DateField(help_text='Conference start date')
    end_date = models.DateField(help_text='Conference end date')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "conferences"

    def __str__(self):
        return self.name
