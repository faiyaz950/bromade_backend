from rest_framework import generics, response, status

from apps.catalog.models import ServicePackage
from apps.locations.models import City

from .serializers import CouponListQuerySerializer, CouponOfferSerializer, CouponValidateSerializer
from .services import CouponService


def _first_error(errors):
    if isinstance(errors, dict):
        for value in errors.values():
            message = _first_error(value)
            if message:
                return message
    if isinstance(errors, list) and errors:
        return _first_error(errors[0])
    if isinstance(errors, str):
        return errors
    return str(errors) if errors else 'This coupon isn’t valid on this booking.'


class CouponValidateView(generics.GenericAPIView):
    serializer_class = CouponValidateSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            detail = _first_error(serializer.errors)
            return response.Response(
                {'detail': detail, **serializer.errors, 'valid': False},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return response.Response(serializer.data)


class CouponListView(generics.GenericAPIView):
    def get(self, request, *args, **kwargs):
        query = CouponListQuerySerializer(data=request.query_params)
        if not query.is_valid():
            detail = _first_error(query.errors)
            return response.Response(
                {'detail': detail, **query.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        package = (
            ServicePackage.objects.select_related('service')
            .filter(pk=query.validated_data['package_id'])
            .first()
        )
        if package is None:
            return response.Response(
                {'detail': 'This service package was not found. Open the service again and retry.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        city = None
        city_id = query.validated_data.get('city_id')
        if city_id:
            city = City.objects.filter(pk=city_id).first()
        offers = CouponService.list_offers(user=request.user, package=package, city=city)
        return response.Response(CouponOfferSerializer(offers, many=True).data)
