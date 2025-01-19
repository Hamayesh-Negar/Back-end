from rest_framework.filters import BaseFilterBackend


class CustomSearchFilter(BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        first_name = request.query_params.get('first_name', None)
        last_name = request.query_params.get('last_name', None)
        telephone = request.query_params.get('telephone', None)
        email = request.query_params.get('email', None)
        unique_code = request.query_params.get('unique_code', None)
        hashed_unique_code = request.query_params.get('hashed_unique_code', None)

        if first_name:
            queryset = queryset.filter(first_name__icontains=first_name)
        if last_name:
            queryset = queryset.filter(last_name__icontains=last_name)
        if telephone:
            queryset = queryset.filter(telephone__icontains=telephone)
        if email:
            queryset = queryset.filter(email__icontains=email)
        if unique_code:
            queryset = queryset.filter(unique_code__iexact=unique_code)
        if hashed_unique_code:
            queryset = queryset.filter(hashed_unique_code__iexact=hashed_unique_code)

        return queryset
