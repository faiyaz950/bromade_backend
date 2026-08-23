from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.bookings.models import Booking, BookingAssignment, BookingItem, BookingStatusLog
from apps.catalog.models import Category, CityPackagePrice, Service, ServicePackage
from apps.locations.models import Address, City
from apps.partners.models import PartnerCity, PartnerProfile, PartnerService


class PartnerAssignmentTests(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(phone_number='+919999999999')
        self.partner_user = User.objects.create_user(phone_number='+919888888801')
        self.partner_user_2 = User.objects.create_user(phone_number='+919888888802')

        self.city = City.objects.create(name='Mumbai', slug='mumbai', state='Maharashtra')
        self.address = Address.objects.create(
            user=self.customer,
            city=self.city,
            label='Home',
            contact_name='Test User',
            contact_phone='+919999999999',
            line1='Powai Lake Road',
            pincode='400076',
            is_default=True,
        )
        category = Category.objects.create(name='Cleaning', description='Cleaning services')
        self.service = Service.objects.create(category=category, name='Bathroom Cleaning', short_description='Deep clean')
        self.package = ServicePackage.objects.create(
            service=self.service,
            name='Classic Bathroom Clean',
            description='Package',
            base_price=1200,
            discounted_price=999,
        )
        CityPackagePrice.objects.create(city=self.city, package=self.package, price=1200, discounted_price=999)

        self.partner = PartnerProfile.objects.create(
            user=self.partner_user,
            full_name='Ravi Kumar',
            is_active=True,
            approval_status=PartnerProfile.ApprovalStatus.APPROVED,
        )
        self.partner_2 = PartnerProfile.objects.create(
            user=self.partner_user_2,
            full_name='Anita Desai',
            is_active=True,
            approval_status=PartnerProfile.ApprovalStatus.APPROVED,
        )
        PartnerCity.objects.create(partner=self.partner, city=self.city)
        PartnerCity.objects.create(partner=self.partner_2, city=self.city)
        PartnerService.objects.create(partner=self.partner, service=self.service)
        PartnerService.objects.create(partner=self.partner_2, service=self.service)

        self.client.force_authenticate(user=self.customer)

    def _create_and_pay_booking(self):
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
        return booking_id

    def test_auto_assignment_on_payment_confirmation(self):
        booking_id = self._create_and_pay_booking()
        booking = Booking.objects.get(pk=booking_id)
        self.assertEqual(booking.assignment_status, Booking.AssignmentStatus.PENDING)
        self.assertEqual(booking.assignments.filter(status=BookingAssignment.Status.PENDING).count(), 1)

    def test_partner_can_list_and_accept_job(self):
        booking_id = self._create_and_pay_booking()
        assignment = BookingAssignment.objects.get(booking_id=booking_id)

        self.client.force_authenticate(user=self.partner_user)
        list_response = self.client.get('/api/v1/partner/jobs/')
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)
        self.assertEqual(list_response.data[0]['id'], booking_id)

        accept_response = self.client.post(f'/api/v1/partner/jobs/assignments/{assignment.id}/accept/')
        self.assertEqual(accept_response.status_code, status.HTTP_200_OK)

        booking = Booking.objects.get(pk=booking_id)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, BookingAssignment.Status.ACCEPTED)
        self.assertEqual(booking.assignment_status, Booking.AssignmentStatus.ACCEPTED)

    def test_partner_reject_triggers_reassignment(self):
        booking_id = self._create_and_pay_booking()
        first_assignment = BookingAssignment.objects.get(booking_id=booking_id, partner=self.partner)

        self.client.force_authenticate(user=self.partner_user)
        reject_response = self.client.post(
            f'/api/v1/partner/jobs/assignments/{first_assignment.id}/reject/',
            {'reason': 'Busy'},
            format='json',
        )
        self.assertEqual(reject_response.status_code, status.HTTP_200_OK)

        first_assignment.refresh_from_db()
        self.assertEqual(first_assignment.status, BookingAssignment.Status.REJECTED)

        second_assignment = BookingAssignment.objects.get(
            booking_id=booking_id,
            partner=self.partner_2,
            status=BookingAssignment.Status.PENDING,
        )
        self.assertIsNotNone(second_assignment)

        self.client.force_authenticate(user=self.partner_user_2)
        jobs_response = self.client.get('/api/v1/partner/jobs/')
        self.assertEqual(len(jobs_response.data), 1)

    def test_non_partner_cannot_access_partner_jobs(self):
        self.client.force_authenticate(user=self.customer)
        response = self.client.get('/api/v1/partner/jobs/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
