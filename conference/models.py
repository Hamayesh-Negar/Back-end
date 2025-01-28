from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.text import slugify


class Conference(models.Model):
    name = models.CharField(help_text='Conference name', max_length=75)
    slug = models.SlugField(max_length=100, unique=True, blank=True, help_text='Conference slug')
    description = models.TextField(help_text='Conference description', null=True, blank=True)
    start_date = models.DateField(help_text='Conference start date')
    end_date = models.DateField(help_text='Conference end date')
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey('user.User', on_delete=models.SET_NULL, null=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "conferences"
        ordering = ['-start_date']
        permissions = [
            ("edit_all_fields", "Can edit all conference fields"),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
            org_slug = self.slug
            if Conference.objects.filter(slug=self.slug).exists():
                self.slug = f"{org_slug}-{self.id}"
        super().save(*args, **kwargs)


@receiver(post_save, sender=Conference)
def update_conference_status(sender, instance, **kwargs):
    today = timezone.now().date()

    if today > instance.end_date and instance.is_active:
        Conference.objects.filter(pk=instance.pk).update(is_active=False)
