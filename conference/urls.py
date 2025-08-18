from django.urls import include, path
from rest_framework_nested import routers

import conference.views
from person.views import PersonViewSet, CategoryViewSet, TaskViewSet

router = routers.DefaultRouter()

router.register(
    r'conferences', conference.views.ConferenceViewSet, basename='conference')
router.register(r'my_invitations',
                conference.views.UserInvitationViewSet, basename='user-invitations')

conference_router = routers.NestedDefaultRouter(
    router, r'conferences', lookup='conference')

conference_router.register(r'persons', PersonViewSet,
                           basename='conference-persons')
conference_router.register(
    r'categories', CategoryViewSet, basename='conference-categories')

conference_router.register(r'tasks', TaskViewSet, basename='conference-tasks')

conference_router.register(
    r'roles', conference.views.ConferenceRoleViewSet, basename='conference-roles')
conference_router.register(
    r'permissions', conference.views.ConferencePermissionViewSet, basename='conference-permissions')
conference_router.register(
    r'members', conference.views.ConferenceMemberViewSet, basename='conference-members')
conference_router.register(
    r'invitations', conference.views.ConferenceInvitationViewSet, basename='conference-invitations')

app_name = 'conference'

urlpatterns = [
    path('', include(router.urls)),
    path('', include(conference_router.urls))
]
