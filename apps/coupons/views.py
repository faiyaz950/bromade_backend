from rest_framework import generics, response, status

from .serializers import CouponValidateSerializer


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
