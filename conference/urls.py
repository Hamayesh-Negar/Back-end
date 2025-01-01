from django.urls import path, include
from rest_framework import routers

from conference.views import ConferenceViewSet

router = routers.DefaultRouter()
router.register(r'conferences', ConferenceViewSet)

app_name = 'conference'

urlpatterns = [
    path('', include(router.urls))
]
