from django.urls import path

from .views import (
    PartnerJobAcceptView,
    PartnerJobDetailView,
    PartnerJobListView,
    PartnerJobRejectView,
    PartnerMeView,
)

urlpatterns = [
    path('me/', PartnerMeView.as_view(), name='partner-me'),
    path('jobs/', PartnerJobListView.as_view(), name='partner-job-list'),
    path('jobs/<uuid:pk>/', PartnerJobDetailView.as_view(), name='partner-job-detail'),
    path('jobs/assignments/<uuid:pk>/accept/', PartnerJobAcceptView.as_view(), name='partner-job-accept'),
    path('jobs/assignments/<uuid:pk>/reject/', PartnerJobRejectView.as_view(), name='partner-job-reject'),
]
