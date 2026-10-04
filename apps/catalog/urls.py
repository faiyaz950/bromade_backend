from django.urls import path

from .views import CategoryListView, HomeHeroSlideListView, PackageDetailView, ServiceReviewsView

urlpatterns = [
    path('categories/', CategoryListView.as_view(), name='category-list'),
    path('home-slides/', HomeHeroSlideListView.as_view(), name='home-slide-list'),
    path('packages/<uuid:id>/', PackageDetailView.as_view(), name='package-detail'),
    path('services/<uuid:id>/reviews/', ServiceReviewsView.as_view(), name='service-reviews'),
]
