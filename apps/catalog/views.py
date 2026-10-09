from datetime import timedelta

from django.db.models import Count, Prefetch
from django.utils import timezone
from rest_framework import generics, permissions, response

from apps.bookings.models import Booking, BookingItem, BookingRating
from apps.bookings.reviews import rating_summary, ratings_for_service

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


POPULAR_WINDOW_DAYS = 30


def service_stats() -> dict:
    """Real ratings and recent booking counts per service id."""
    since = timezone.now() - timedelta(days=POPULAR_WINDOW_DAYS)
    booked = (
        BookingItem.objects.filter(
            booking__created_at__gte=since,
            booking__status__in=[Booking.Status.CONFIRMED, Booking.Status.COMPLETED],
        )
        .values('package__service_id')
        .annotate(n=Count('booking', distinct=True))
        .values_list('package__service_id', 'n')
    )
    stats = {service_id: {'recent_bookings': n} for service_id, n in booked}
    # A booking with two packages of one service must still count as one review.
    stars_by_service: dict = {}
    rows = BookingRating.objects.values_list('booking__items__package__service_id', 'id', 'stars').distinct()
    for service_id, rating_id, stars in rows:
        stars_by_service.setdefault(service_id, {})[rating_id] = stars
    for service_id, ratings in stars_by_service.items():
        entry = stats.setdefault(service_id, {})
        entry['rating_count'] = len(ratings)
        entry['rating_average'] = round(sum(ratings.values()) / len(ratings), 1)
    return stats


class CategoryListView(generics.ListAPIView):
    serializer_class = CategorySerializer

    def get_queryset(self):
        city_id = self.request.query_params.get('city_id')
        return Category.objects.filter(is_active=True).prefetch_related(
            'services__inclusions',
            'services__process_steps',
            Prefetch(
                'services__packages',
                queryset=ServicePackage.objects.prefetch_related('inclusions', _city_price_prefetch(city_id)),
            ),
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['city_id'] = self.request.query_params.get('city_id')
        context['service_stats'] = service_stats()
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
            .prefetch_related('inclusions', _city_price_prefetch(city_id))
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['city_id'] = self.request.query_params.get('city_id')
        return context


class ServiceReviewsView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, id):
        return response.Response(
            rating_summary(ratings_for_service(id), request=request, limit=15, with_photos=True)
        )
