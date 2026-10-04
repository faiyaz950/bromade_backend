from django.urls import path

from .views import (
    SupportContactView,
    SupportMessageCreateView,
    SupportTicketDetailView,
    SupportTicketListView,
    SupportUnreadView,
)

urlpatterns = [
    path('contact/', SupportContactView.as_view(), name='support-contact'),
    path('unread/', SupportUnreadView.as_view(), name='support-unread'),
    path('tickets/', SupportTicketListView.as_view(), name='support-tickets'),
    path('tickets/<uuid:pk>/', SupportTicketDetailView.as_view(), name='support-ticket-detail'),
    path('tickets/<uuid:pk>/messages/', SupportMessageCreateView.as_view(), name='support-ticket-messages'),
]
