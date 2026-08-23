from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.locations.models import Address, City


class AddressAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone_number='+919222222222')
        self.client.force_authenticate(user=self.user)
        self.city = City.objects.create(name='Pune', slug='pune', state='Maharashtra')

    def test_create_address_and_set_default(self):
        create_response = self.client.post(
            '/api/v1/addresses/',
            {
                'label': 'Home',
                'contact_name': 'Test User',
                'contact_phone': '+919222222222',
                'line1': 'Baner Road',
                'line2': '',
                'landmark': '',
                'pincode': '411045',
                'city_id': str(self.city.id),
                'is_default': True,
            },
            format='json',
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        second = Address.objects.create(
            user=self.user,
            city=self.city,
            label='Office',
            contact_name='Test User',
            contact_phone='+919222222222',
            line1='Hinjewadi',
            pincode='411057',
            is_default=False,
        )
        set_default = self.client.post(f'/api/v1/addresses/{second.id}/set-default/')
        self.assertEqual(set_default.status_code, status.HTTP_200_OK)
        second.refresh_from_db()
        self.assertTrue(second.is_default)
        self.assertEqual(Address.objects.filter(user=self.user, is_default=True).count(), 1)
