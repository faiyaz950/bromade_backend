from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.bookings.models import Booking, BookingAssignment
from apps.catalog.models import Category, CityPackagePrice, Service, ServicePackage
from apps.locations.models import Address, City


class BookingAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone_number='+919999999999')
        self.client.force_authenticate(user=self.user)
        self.city = City.objects.create(name='Mumbai', slug='mumbai', state='Maharashtra')
        self.address = Address.objects.create(
            user=self.user,
            city=self.city,
            label='Home',
            contact_name='Test User',
            contact_phone='+919999999999',
            line1='Powai Lake Road',
            pincode='400076',
            is_default=True,
        )
        category = Category.objects.create(name='Cleaning', description='Cleaning services')
        service = Service.objects.create(category=category, name='Bathroom Cleaning', short_description='Deep clean')
        self.package = ServicePackage.objects.create(
            service=service,
            name='Classic Bathroom Clean',
            description='Package',
            base_price=1200,
            discounted_price=999,
        )
        CityPackagePrice.objects.create(city=self.city, package=self.package, price=1200, discounted_price=999)

    def test_create_booking_and_payment(self):
        booking_response = self.client.post(
            '/api/v1/bookings/create/',
            {
                'package_id': str(self.package.id),
                'address_id': str(self.address.id),
                'scheduled_date': (timezone.localdate() + timedelta(days=1)).isoformat(),
                'scheduled_time': '10:30:00',
                'quantity': 1,
            },
            format='json',
        )
        self.assertEqual(booking_response.status_code, status.HTTP_201_CREATED)
        booking_id = booking_response.data['id']

        payment_order = self.client.post('/api/v1/payments/orders/', {'booking_id': booking_id}, format='json')
        self.assertEqual(payment_order.status_code, status.HTTP_201_CREATED)

        verify_response = self.client.post(
            '/api/v1/payments/verify/',
            {
                'gateway_order_id': payment_order.data['gateway_order_id'],
                'gateway_payment_id': 'pay_mock123',
            },
            format='json',
        )
        self.assertEqual(verify_response.status_code, status.HTTP_200_OK)
        self.assertEqual(verify_response.data['booking_status'], 'confirmed')

        booking = Booking.objects.get(pk=booking_id)
        self.assertEqual(booking.assignment_status, Booking.AssignmentStatus.UNASSIGNED)
        self.assertEqual(booking.assignments.count(), 0)

    def test_cannot_book_in_city_marked_available_soon(self):
        soon_city = City.objects.create(
            name='Lucknow',
            slug='lucknow',
            state='Uttar Pradesh',
            is_active=False,
        )
        soon_address = Address.objects.create(
            user=self.user,
            city=soon_city,
            label='Parents',
            contact_name='Test User',
            contact_phone='+919999999999',
            line1='Hazratganj',
            pincode='226001',
        )
        response = self.client.post(
            '/api/v1/bookings/create/',
            {
                'package_id': str(self.package.id),
                'address_id': str(soon_address.id),
                'scheduled_date': (timezone.localdate() + timedelta(days=1)).isoformat(),
                'scheduled_time': '10:30:00',
                'quantity': 1,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('address_id', response.data)
