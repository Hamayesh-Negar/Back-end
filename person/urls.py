from django.urls import include, path
from rest_framework_nested import routers

from person.views import PersonViewSet, CategoryViewSet, TaskViewSet, PersonTaskViewSet

router = routers.DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'persons', PersonViewSet, basename='person')
router.register(r'tasks', TaskViewSet, basename='task')
router.register(r'person_tasks', PersonTaskViewSet, basename='person_task')

categories_router = routers.NestedDefaultRouter(
    router, r'categories', lookup='category')
categories_router.register(r'persons', PersonViewSet,
                           basename='category-persons')

persons_router = routers.NestedDefaultRouter(
    router, r'persons', lookup='person')
persons_router.register(r'tasks', TaskViewSet, basename='person-tasks')
persons_router.register(
    r'person_tasks', PersonTaskViewSet, basename='person-task')

task_router = routers.NestedDefaultRouter(router, r'tasks', lookup='task')
task_router.register(r'person_tasks', PersonTaskViewSet,
                     basename='task-person-tasks')

app_name = 'person'

urlpatterns = [
    path('', include(router.urls)),
    path('', include(categories_router.urls)),
    path('', include(persons_router.urls)),
    path('', include(task_router.urls)),
]
