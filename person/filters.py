from django_filters import rest_framework as filters

import person


class PersonFilter(filters.FilterSet):
    first_name = filters.CharFilter(lookup_expr='icontains')
    last_name = filters.CharFilter(lookup_expr='icontains')


    class Meta:
        model = person
        fields = ['first_name', 'last_name']