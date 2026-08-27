from rest_framework import generics, response


from .serializers import CouponValidateSerializer


class CouponValidateView(generics.GenericAPIView):
    serializer_class = CouponValidateSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return response.Response(serializer.data)
