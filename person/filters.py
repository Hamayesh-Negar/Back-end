from django_filters import rest_framework as filters

import person


class PersonFilter(filters.FilterSet):
    first_name = filters.CharFilter(lookup_expr='icontains')
    last_name = filters.CharFilter(lookup_expr='icontains')
    telephone = filters.CharFilter(lookup_expr='icontains')
    email = filters.CharFilter(lookup_expr='icontains')
    unique_code = filters.CharFilter(lookup_expr='iexact')
    hashed_unique_code = filters.CharFilter(lookup_expr='iexact')

    class Meta:
        model = person
        fields = ['first_name', 'last_name', 'telephone',
                  'email', 'unique_code', 'hashed_unique_code']