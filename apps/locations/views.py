from rest_framework import generics, response, status
from rest_framework.views import APIView

from .models import Address, City
from .serializers import AddressSerializer, CitySerializer


class CityListView(generics.ListAPIView):
    queryset = City.objects.filter(is_active=True).order_by('name')
    serializer_class = CitySerializer


class AddressListCreateView(generics.ListCreateAPIView):
    serializer_class = AddressSerializer

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user).select_related('city')


class AddressDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AddressSerializer

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user).select_related('city')


class AddressSetDefaultView(APIView):
    def post(self, request, pk):
        address = Address.objects.filter(user=request.user, pk=pk).select_related('city').first()
        if address is None:
            return response.Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        Address.objects.filter(user=request.user, is_default=True).update(is_default=False)
        address.is_default = True
        address.save(update_fields=['is_default', 'updated_at'])
        return response.Response(AddressSerializer(address).data)
