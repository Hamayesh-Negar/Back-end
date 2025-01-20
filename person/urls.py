from django.urls import include, path
from rest_framework_nested import routers

import conference.views
from person.views import PersonViewSet, CategoryViewSet, TaskViewSet, PersonTaskViewSet

router = routers.DefaultRouter()
router.register(r'conferences', conference.views.ConferenceViewSet, basename='conference')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'persons', PersonViewSet, basename='person')
router.register(r'tasks', TaskViewSet, basename='task')
router.register(r'person_tasks', PersonTaskViewSet, basename='person_task')

conference_router = routers.NestedDefaultRouter(router, r'conferences', lookup='conference')
conference_router.register(r'persons', PersonViewSet, basename='conference-persons')
conference_router.register(r'categories', CategoryViewSet, basename='conference-categories')
conference_router.register(r'tasks', TaskViewSet, basename='conference-tasks')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(conference_router.urls)),
]
