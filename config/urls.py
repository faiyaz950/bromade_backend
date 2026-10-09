from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.static import serve
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.common.views import app_release, delete_account, health, privacy_policy, terms

urlpatterns = [
    path('health/', health, name='health'),
    path('privacy/', privacy_policy, name='privacy-policy'),
    path('terms/', terms, name='terms'),
    path('delete-account/', delete_account, name='delete-account'),
    path('admin/', admin.site.urls),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/v1/app-release/', app_release, name='app-release'),
    path('api/v1/auth/', include('apps.accounts.urls')),
    path('api/v1/', include('apps.locations.urls')),
    path('api/v1/catalog/', include('apps.catalog.urls')),
    path('api/v1/bookings/', include('apps.bookings.urls')),
    path('api/v1/coupons/', include('apps.coupons.urls')),
    path('api/v1/payments/', include('apps.payments.urls')),
    path('api/v1/partner/', include('apps.partners.urls')),
    path('api/v1/support/', include('apps.customers.urls')),
    path('media/<path:path>', serve, {'document_root': settings.MEDIA_ROOT}),
]

