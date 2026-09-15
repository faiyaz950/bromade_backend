from django.db.models import Prefetch
from rest_framework import generics

from .models import Category, CityPackagePrice, HomeHeroSlide, ServicePackage
from .serializers import CategorySerializer, HomeHeroSlideSerializer, PackageDetailSerializer


def _city_price_prefetch(city_id):
    """Prefetch only the matching city price per package (instead of the
    serializer re-querying `city_prices` per package, twice, on every
    request — see ServicePackageSerializer._city_price)."""
    queryset = CityPackagePrice.objects.filter(is_active=True)
    if city_id:
        queryset = queryset.filter(city_id=city_id)
    else:
        queryset = queryset.none()
    return Prefetch('city_prices', queryset=queryset, to_attr='matched_city_prices')


class CategoryListView(generics.ListAPIView):
    serializer_class = CategorySerializer

    def get_queryset(self):
        city_id = self.request.query_params.get('city_id')
        return Category.objects.filter(is_active=True).prefetch_related(
            'services__inclusions',
            'services__process_steps',
            Prefetch(
                'services__packages',
                queryset=ServicePackage.objects.prefetch_related(_city_price_prefetch(city_id)),
            ),
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['city_id'] = self.request.query_params.get('city_id')
        return context


class HomeHeroSlideListView(generics.ListAPIView):
    serializer_class = HomeHeroSlideSerializer
    queryset = HomeHeroSlide.objects.filter(is_active=True)


class PackageDetailView(generics.RetrieveAPIView):
    serializer_class = PackageDetailSerializer
    lookup_field = 'id'

    def get_queryset(self):
        city_id = self.request.query_params.get('city_id')
        return (
            ServicePackage.objects.filter(is_active=True)
            .select_related('service__category')
            .prefetch_related(_city_price_prefetch(city_id))
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['city_id'] = self.request.query_params.get('city_id')
        return context
