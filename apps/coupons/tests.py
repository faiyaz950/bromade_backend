from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.bookings.models import Booking
from apps.catalog.models import Category, CityPackagePrice, Service, ServicePackage
from apps.coupons.models import Coupon, CouponRedemption
from apps.locations.models import Address, City


class CouponAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone_number='+919888888888')
        self.other = User.objects.create_user(phone_number='+919777777777')
        self.client.force_authenticate(user=self.user)
        self.city = City.objects.create(name='Pune', slug='pune', state='Maharashtra')
        self.other_city = City.objects.create(name='Delhi', slug='delhi', state='Delhi')
        self.address = Address.objects.create(
            user=self.user,
            city=self.city,
            label='Home',
            contact_name='Test User',
            contact_phone='+919888888888',
            line1='Koregaon Park',
            pincode='411001',
            is_default=True,
        )
        category = Category.objects.create(name='Cleaning', description='Cleaning services')
        self.service = Service.objects.create(category=category, name='Kitchen Cleaning', short_description='Deep clean')
        self.package = ServicePackage.objects.create(
            service=self.service,
            name='Classic Kitchen Clean',
            description='Package',
            base_price=1500,
            discounted_price=1000,
        )
        CityPackagePrice.objects.create(city=self.city, package=self.package, price=1500, discounted_price=1000)
        self.coupon = Coupon.objects.create(
            code='save100',
            title='Flat hundred',
            discount_type=Coupon.DiscountType.FIXED,
            discount_value=Decimal('100.00'),
            usage_limit_per_user=1,
        )

    def _booking_payload(self, coupon_code='SAVE100'):
        return {
            'package_id': str(self.package.id),
            'address_id': str(self.address.id),
            'scheduled_date': (timezone.localdate() + timedelta(days=1)).isoformat(),
            'scheduled_time': '11:00:00',
            'quantity': 1,
            'coupon_code': coupon_code,
        }

    def test_validate_and_apply_fixed_coupon(self):
        response = self.client.post(
            '/api/v1/coupons/validate/',
            {
                'code': 'save100',
                'package_id': str(self.package.id),
                'city_id': str(self.city.id),
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['code'], 'SAVE100')
        self.assertEqual(Decimal(response.data['discount_amount']), Decimal('100.00'))
        self.assertEqual(Decimal(response.data['total_amount']), Decimal('900.00'))

        booking_response = self.client.post('/api/v1/bookings/create/', self._booking_payload(), format='json')
        self.assertEqual(booking_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(booking_response.data['coupon_code'], 'SAVE100')
        self.assertEqual(Decimal(booking_response.data['discount_amount']), Decimal('100.00'))
        self.assertEqual(Decimal(booking_response.data['total_amount']), Decimal('900.00'))
        self.assertEqual(CouponRedemption.objects.count(), 1)

        payment = self.client.post(
            '/api/v1/payments/orders/',
            {'booking_id': booking_response.data['id'], 'method': 'cash'},
            format='json',
        )
        self.assertEqual(payment.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Decimal(str(payment.data.get('amount', '900'))), Decimal('900.00'))

    def test_percentage_coupon_respects_max_discount(self):
        Coupon.objects.create(
            code='PCT20',
            title='Twenty percent',
            discount_type=Coupon.DiscountType.PERCENTAGE,
            discount_value=Decimal('20.00'),
            max_discount_amount=Decimal('150.00'),
        )
        response = self.client.post(
            '/api/v1/coupons/validate/',
            {'code': 'PCT20', 'package_id': str(self.package.id), 'city_id': str(self.city.id)},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(response.data['discount_amount']), Decimal('150.00'))
        self.assertEqual(Decimal(response.data['total_amount']), Decimal('850.00'))

    def test_rejects_expired_and_min_order_and_reuse(self):
        Coupon.objects.create(
            code='OLDONE',
            title='Expired',
            discount_type=Coupon.DiscountType.FIXED,
            discount_value=Decimal('50.00'),
            valid_until=timezone.localdate() - timedelta(days=1),
        )
        expired = self.client.post(
            '/api/v1/coupons/validate/',
            {'code': 'OLDONE', 'package_id': str(self.package.id)},
            format='json',
        )
        self.assertEqual(expired.status_code, status.HTTP_400_BAD_REQUEST)

        Coupon.objects.create(
            code='BIGMIN',
            title='High minimum',
            discount_type=Coupon.DiscountType.FIXED,
            discount_value=Decimal('50.00'),
            min_order_amount=Decimal('2000.00'),
        )
        too_small = self.client.post(
            '/api/v1/coupons/validate/',
            {'code': 'BIGMIN', 'package_id': str(self.package.id), 'city_id': str(self.city.id)},
            format='json',
        )
        self.assertEqual(too_small.status_code, status.HTTP_400_BAD_REQUEST)

        first = self.client.post('/api/v1/bookings/create/', self._booking_payload(), format='json')
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        reuse = self.client.post('/api/v1/bookings/create/', self._booking_payload(), format='json')
        self.assertEqual(reuse.status_code, status.HTTP_400_BAD_REQUEST)

    def test_city_scoped_coupon(self):
        scoped = Coupon.objects.create(
            code='PUNEONLY',
            title='Pune special',
            discount_type=Coupon.DiscountType.FIXED,
            discount_value=Decimal('50.00'),
        )
        scoped.cities.add(self.other_city)
        response = self.client.post(
            '/api/v1/coupons/validate/',
            {'code': 'PUNEONLY', 'package_id': str(self.package.id), 'city_id': str(self.city.id)},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_booking_without_coupon_is_unchanged(self):
        payload = self._booking_payload()
        payload.pop('coupon_code')
        response = self.client.post('/api/v1/bookings/create/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        booking = Booking.objects.get(pk=response.data['id'])
        self.assertEqual(booking.discount_amount, Decimal('0.00'))
        self.assertEqual(booking.total_amount, Decimal('1000.00'))
        self.assertEqual(booking.coupon_code, '')

    def test_all_services_coupon_works_on_any_service(self):
        coupon = Coupon.objects.create(
            code='EVERYWHERE',
            title='Site wide',
            discount_type=Coupon.DiscountType.FIXED,
            discount_value=Decimal('50.00'),
            apply_scope=Coupon.ApplyScope.ALL_SERVICES,
        )
        bathroom = Service.objects.create(
            category=self.service.category,
            name='Bathroom Cleaning',
            short_description='Bath',
        )
        bath_package = ServicePackage.objects.create(
            service=bathroom,
            name='Classic Bathroom Clean',
            description='Package',
            base_price=1200,
            discounted_price=900,
        )
        response = self.client.post(
            '/api/v1/coupons/validate/',
            {'code': coupon.code, 'package_id': str(bath_package.id), 'city_id': str(self.city.id)},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_selected_service_coupon_rejects_other_services(self):
        bathroom = Service.objects.create(
            category=self.service.category,
            name='Bathroom Cleaning',
            short_description='Bath',
        )
        bath_package = ServicePackage.objects.create(
            service=bathroom,
            name='Classic Bathroom Clean',
            description='Package',
            base_price=1200,
            discounted_price=900,
        )
        coupon = Coupon.objects.create(
            code='KITCHENONLY',
            title='Kitchen only',
            discount_type=Coupon.DiscountType.FIXED,
            discount_value=Decimal('50.00'),
            apply_scope=Coupon.ApplyScope.SELECTED_SERVICES,
        )
        coupon.services.add(self.service)

        allowed = self.client.post(
            '/api/v1/coupons/validate/',
            {'code': 'KITCHENONLY', 'package_id': str(self.package.id), 'city_id': str(self.city.id)},
            format='json',
        )
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)

        blocked = self.client.post(
            '/api/v1/coupons/validate/',
            {'code': 'KITCHENONLY', 'package_id': str(bath_package.id), 'city_id': str(self.city.id)},
            format='json',
        )
        self.assertEqual(blocked.status_code, status.HTTP_400_BAD_REQUEST)
