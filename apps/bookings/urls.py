from django.urls import path

from .views import (
    BookingConfirmView,
    BookingCreateView,
    BookingDetailView,
    BookingListView,
    BookingPriceSummaryView,
    BookingRateView,
)

urlpatterns = [
    path('price-summary/', BookingPriceSummaryView.as_view(), name='booking-price-summary'),
    path('', BookingListView.as_view(), name='booking-list'),
    path('create/', BookingCreateView.as_view(), name='booking-create'),
    path('<uuid:pk>/confirm/', BookingConfirmView.as_view(), name='booking-confirm'),
    path('<uuid:pk>/rate/', BookingRateView.as_view(), name='booking-rate'),
    path('<uuid:pk>/', BookingDetailView.as_view(), name='booking-detail'),
]
