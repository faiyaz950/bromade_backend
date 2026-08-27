from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.static import serve
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.common.views import health

urlpatterns = [
    path('health/', health, name='health'),
    path('admin/', admin.site.urls),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/v1/auth/', include('apps.accounts.urls')),
    path('api/v1/', include('apps.locations.urls')),
    path('api/v1/catalog/', include('apps.catalog.urls')),
    path('api/v1/bookings/', include('apps.bookings.urls')),
    path('api/v1/coupons/', include('apps.coupons.urls')),
    path('api/v1/payments/', include('apps.payments.urls')),
    path('api/v1/partner/', include('apps.partners.urls')),
    path('media/<path:path>', serve, {'document_root': settings.MEDIA_ROOT}),
]

