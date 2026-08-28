from django.urls import path

from .views import (
    AddressDetailView,
    AddressListCreateView,
    AddressSetDefaultView,
    CityListView,
    CoverageCheckView,
)

urlpatterns = [
    path('cities/', CityListView.as_view(), name='city-list'),
    path('coverage/', CoverageCheckView.as_view(), name='service-coverage'),
    path('addresses/', AddressListCreateView.as_view(), name='address-list-create'),
    path('addresses/<uuid:pk>/', AddressDetailView.as_view(), name='address-detail'),
    path('addresses/<uuid:pk>/set-default/', AddressSetDefaultView.as_view(), name='address-set-default'),
]
