from rest_framework.filters import BaseFilterBackend
import django_filters
from person.models import Person


class PersonFilter(django_filters.FilterSet):
    category = django_filters.NumberFilter(
        field_name='categories', lookup_expr='exact')

    class Meta:
        model = Person
        fields = ['is_active', 'category']
