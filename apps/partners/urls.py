from django.urls import path

from .views import (
    PartnerCashCollectView,
    PartnerDeviceTokenView,
    PartnerEarningsView,
    PartnerJobAcceptView,
    PartnerJobDetailView,
    PartnerJobListView,
    PartnerJobRejectView,
    PartnerMeView,
    PartnerUnavailableDateDeleteView,
    PartnerUnavailableDateListView,
    PartnerVisitAdvanceView,
)

urlpatterns = [
    path('me/', PartnerMeView.as_view(), name='partner-me'),
    path('me/device-token/', PartnerDeviceTokenView.as_view(), name='partner-device-token'),
    path('earnings/', PartnerEarningsView.as_view(), name='partner-earnings'),
    path('unavailable-dates/', PartnerUnavailableDateListView.as_view(), name='partner-unavailable-dates'),
    path(
        'unavailable-dates/<uuid:pk>/',
        PartnerUnavailableDateDeleteView.as_view(),
        name='partner-unavailable-date-delete',
    ),
    path('jobs/', PartnerJobListView.as_view(), name='partner-job-list'),
    path('jobs/<uuid:pk>/', PartnerJobDetailView.as_view(), name='partner-job-detail'),
    path('jobs/assignments/<uuid:pk>/accept/', PartnerJobAcceptView.as_view(), name='partner-job-accept'),
    path('jobs/assignments/<uuid:pk>/reject/', PartnerJobRejectView.as_view(), name='partner-job-reject'),
    path('jobs/assignments/<uuid:pk>/visit/', PartnerVisitAdvanceView.as_view(), name='partner-job-visit'),
    path(
        'jobs/assignments/<uuid:pk>/collect-cash/',
        PartnerCashCollectView.as_view(),
        name='partner-job-collect-cash',
    ),
]
