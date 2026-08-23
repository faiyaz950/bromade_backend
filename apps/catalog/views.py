from rest_framework import generics

from .models import Category, ServicePackage
from .serializers import CategorySerializer, PackageDetailSerializer


class CategoryListView(generics.ListAPIView):
    serializer_class = CategorySerializer

    def get_queryset(self):
        return Category.objects.filter(is_active=True).prefetch_related(
            'services__packages',
            'services__inclusions',
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['city_id'] = self.request.query_params.get('city_id')
        return context


class PackageDetailView(generics.RetrieveAPIView):
    queryset = ServicePackage.objects.filter(is_active=True).select_related('service__category').prefetch_related('city_prices')
    serializer_class = PackageDetailSerializer
    lookup_field = 'id'

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['city_id'] = self.request.query_params.get('city_id')
        return context
