from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenRefreshView

from Hamayesh_Negar_django import settings
from Hamayesh_Negar_django.views import HealthCheckView

urlpatterns = [

    path("v1/", include(
        [
            path('health/', HealthCheckView.as_view(), name='health-check'),
            path('user/', include('user.urls'), name='user'),
            path("conference/", include('conference.urls'), name='conference'),
            path("attendee/", include('person.urls'), name='person'),
            path('auth/token/', TokenRefreshView.as_view(), name='token_refresh'),
            path('admin/', admin.site.urls),
            path('auth/', include('authentication.urls'), name='authentication'),
        ]
    ))
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL,
                          document_root=settings.STATIC_ROOT)
