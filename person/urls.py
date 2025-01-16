from django.urls import include, path
from rest_framework import routers

import conference.views
from person.views import PersonViewSet, CategoryViewSet, TaskViewSet, PersonTaskViewSet

router = routers.DefaultRouter()
router.register(r'conferences', conference.views.ConferenceViewSet, basename='conference')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'persons', PersonViewSet, basename='person')
router.register(r'tasks', TaskViewSet, basename='task')
router.register(r'person_tasks', PersonTaskViewSet, basename='person_task')

urlpatterns = [
    path('', include(router.urls))
]
