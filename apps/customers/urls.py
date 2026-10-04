from django.urls import path

from .views import SupportContactView, SupportTicketListView

urlpatterns = [
    path('contact/', SupportContactView.as_view(), name='support-contact'),
    path('tickets/', SupportTicketListView.as_view(), name='support-tickets'),
]
