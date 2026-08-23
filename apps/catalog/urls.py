from django.urls import path

from .views import CategoryListView, PackageDetailView

urlpatterns = [
    path('categories/', CategoryListView.as_view(), name='category-list'),
    path('packages/<uuid:id>/', PackageDetailView.as_view(), name='package-detail'),
]
