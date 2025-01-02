from django.urls import include, path
from rest_framework import routers

from person.views import PersonViewSet, CategoryViewSet

router = routers.DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'persons', PersonViewSet, basename='person')

urlpatterns = [
    path('', include(router.urls))
]
