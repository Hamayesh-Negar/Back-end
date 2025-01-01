from django.urls import include, path
from rest_framework import routers

from person.views import PersonViewSet

router = routers.DefaultRouter()
router.register(r'persons', PersonViewSet)

app_name = 'person'

urlpatterns = [
    path('', include(router.urls))
]
