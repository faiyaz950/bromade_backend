from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.locations.models import Address, City
from apps.locations.services import check_service_coverage, normalize_place


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


class CoverageAPITests(APITestCase):
    def setUp(self):
        self.pune = City.objects.create(
            name='Pune',
            slug='pune',
            state='Maharashtra',
            aliases='Poona',
            latitude=18.5204,
            longitude=73.8567,
            service_radius_km=40,
            is_active=True,
        )
        self.mumbai = City.objects.create(
            name='Mumbai',
            slug='mumbai',
            state='Maharashtra',
            aliases='Bombay, Mumbai City',
            latitude=19.0760,
            longitude=72.8777,
            service_radius_km=45,
            is_active=True,
        )
        self.lucknow = City.objects.create(
            name='Lucknow',
            slug='lucknow',
            state='Uttar Pradesh',
            latitude=26.8467,
            longitude=80.9462,
            is_active=False,
            coming_soon_message='Lucknow partners are onboarding. Hang tight.',
        )

    def test_normalize_strips_city_suffix(self):
        self.assertEqual(normalize_place('Pune City'), 'pune')
        self.assertEqual(normalize_place('New Delhi'), 'new delhi')

    def test_name_and_alias_match_live_city(self):
        result = check_service_coverage(city_name='Bombay')
        self.assertTrue(result['available'])
        self.assertEqual(result['city']['name'], 'Mumbai')

        pune = check_service_coverage(place_names=['Kothrud', 'Pune District'])
        self.assertTrue(pune['available'])
        self.assertEqual(pune['city']['name'], 'Pune')

    def test_inactive_city_is_coming_soon(self):
        result = check_service_coverage(city_name='Lucknow')
        self.assertFalse(result['available'])
        self.assertEqual(result['city']['name'], 'Lucknow')
        self.assertEqual(result['message'], 'Lucknow partners are onboarding. Hang tight.')
        self.assertEqual(len(result['available_cities']), 2)

    def test_unknown_city_is_coming_soon(self):
        result = check_service_coverage(city_name='Guwahati')
        self.assertFalse(result['available'])
        self.assertIsNone(result['city'])
        self.assertEqual(result['detected_name'], 'Guwahati')
        self.assertIn('available soon', result['message'].lower())

    def test_gps_matches_nearest_live_city(self):
        result = check_service_coverage(latitude=18.53, longitude=73.85)
        self.assertTrue(result['available'])
        self.assertEqual(result['city']['name'], 'Pune')

    def test_gps_outside_radius_falls_back_to_name(self):
        result = check_service_coverage(
            latitude=13.08,
            longitude=80.27,
            city_name='Chennai',
        )
        self.assertFalse(result['available'])
        self.assertEqual(result['detected_name'], 'Chennai')

    def test_selecting_city_id_uses_admin_flag(self):
        live = check_service_coverage(city_id=self.pune.id)
        self.assertTrue(live['available'])
        soon = check_service_coverage(city_id=self.lucknow.id)
        self.assertFalse(soon['available'])

    def test_coverage_endpoint_is_public(self):
        response = self.client.post(
            '/api/v1/coverage/',
            {'city_name': 'Pune', 'place_names': ['Baner']},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['available'])
        self.assertEqual(response.data['city']['name'], 'Pune')

    def test_cities_list_is_public_and_hides_inactive(self):
        response = self.client.get('/api/v1/cities/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = {item['name'] for item in response.data}
        self.assertEqual(names, {'Pune', 'Mumbai'})
