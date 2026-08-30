from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.bookings.models import Booking, BookingAssignment, BookingRating
from apps.catalog.models import Category, CityPackagePrice, Service, ServicePackage
from apps.locations.models import Address, City
from apps.partners.models import PartnerCity, PartnerProfile, PartnerService, PartnerUnavailableDate
from apps.payments.models import Payment


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
        self.client.force_authenticate(user=self.customer)
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

    def _create_cash_booking(self):
        self.client.force_authenticate(user=self.customer)
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
        payment_order = self.client.post(
            '/api/v1/payments/orders/',
            {'booking_id': booking_id, 'method': 'cash'},
            format='json',
        )
        self.assertEqual(payment_order.status_code, status.HTTP_201_CREATED)
        return booking_id

    def _accept_assignment(self, booking_id, partner_user=None):
        assignment = BookingAssignment.objects.get(
            booking_id=booking_id,
            status=BookingAssignment.Status.PENDING,
        )
        user = partner_user or assignment.partner.user
        self.client.force_authenticate(user=user)
        accept_response = self.client.post(f'/api/v1/partner/jobs/assignments/{assignment.id}/accept/')
        self.assertEqual(accept_response.status_code, status.HTTP_200_OK)
        return assignment

    def _advance(self, assignment_id, visit_status, checklist=None):
        payload = {'visit_status': visit_status}
        if checklist is not None:
            payload['checklist'] = checklist
        return self.client.post(
            f'/api/v1/partner/jobs/assignments/{assignment_id}/visit/',
            payload,
            format='json',
        )

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

    def test_pending_partner_can_load_profile_but_not_jobs(self):
        pending_user = User.objects.create_user(phone_number='+919888888803')
        PartnerProfile.objects.create(
            user=pending_user,
            full_name='Waiting Partner',
            is_active=False,
            approval_status=PartnerProfile.ApprovalStatus.PENDING,
        )
        self.client.force_authenticate(user=pending_user)
        me = self.client.get('/api/v1/partner/me/')
        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertEqual(me.data['approval_status'], 'pending')
        jobs = self.client.get('/api/v1/partner/jobs/')
        self.assertEqual(jobs.status_code, status.HTTP_403_FORBIDDEN)

    def test_visit_must_advance_one_step_then_complete(self):
        booking_id = self._create_and_pay_booking()
        assignment = self._accept_assignment(booking_id)

        too_early = self._advance(assignment.id, 'completed')
        self.assertEqual(too_early.status_code, status.HTTP_400_BAD_REQUEST)

        skip = self._advance(assignment.id, 'arrived')
        self.assertEqual(skip.status_code, status.HTTP_400_BAD_REQUEST)

        on_way = self._advance(assignment.id, 'on_the_way')
        self.assertEqual(on_way.status_code, status.HTTP_200_OK)
        self.assertEqual(on_way.data['visit_status'], 'on_the_way')

        arrived = self._advance(assignment.id, 'arrived')
        self.assertEqual(arrived.status_code, status.HTTP_200_OK)
        started = self._advance(assignment.id, 'in_progress')
        self.assertEqual(started.status_code, status.HTTP_200_OK)

        completed = self._advance(assignment.id, 'completed')
        self.assertEqual(completed.status_code, status.HTTP_200_OK)
        booking = Booking.objects.get(pk=booking_id)
        self.assertEqual(booking.status, Booking.Status.COMPLETED)
        self.assertEqual(booking.visit_status, Booking.VisitStatus.COMPLETED)
        self.assertTrue(all(item.get('done') for item in booking.checklist))

        accepted = self.client.get('/api/v1/partner/jobs/', {'status': 'accepted'})
        self.assertEqual(accepted.data, [])
        completed = self.client.get('/api/v1/partner/jobs/', {'status': 'completed'})
        self.assertEqual(len(completed.data), 1)
        self.assertEqual(completed.data[0]['id'], booking_id)

        earnings = self.client.get('/api/v1/partner/earnings/')
        self.assertEqual(earnings.status_code, status.HTTP_200_OK)
        self.assertEqual(earnings.data['completed_count'], 1)
        self.assertGreater(float(earnings.data['completed_amount']), 0)

        self.client.force_authenticate(user=self.customer)
        rate = self.client.post(
            f'/api/v1/bookings/{booking_id}/rate/',
            {'stars': 5, 'comment': 'On time and tidy.'},
            format='json',
        )
        self.assertEqual(rate.status_code, status.HTTP_201_CREATED)
        self.assertEqual(rate.data['rating_stars'], 5)
        self.assertEqual(BookingRating.objects.filter(booking_id=booking_id).count(), 1)

        again = self.client.post(
            f'/api/v1/bookings/{booking_id}/rate/',
            {'stars': 4},
            format='json',
        )
        self.assertEqual(again.status_code, status.HTTP_400_BAD_REQUEST)

        self.client.force_authenticate(user=self.partner_user)
        me = self.client.get('/api/v1/partner/me/')
        self.assertEqual(float(me.data['average_rating']), 5.0)
        self.assertEqual(me.data['rating_count'], 1)

    def test_cash_collect_and_auto_collect_on_complete(self):
        booking_id = self._create_cash_booking()
        assignment = self._accept_assignment(booking_id)
        payment = Payment.objects.get(booking_id=booking_id)
        self.assertEqual(payment.status, Payment.Status.CASH_PENDING)

        collect = self.client.post(f'/api/v1/partner/jobs/assignments/{assignment.id}/collect-cash/')
        self.assertEqual(collect.status_code, status.HTTP_200_OK)
        self.assertTrue(collect.data['cash_collected'])
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PAID)

        booking_id_2 = self._create_cash_booking()
        assignment_2 = BookingAssignment.objects.get(
            booking_id=booking_id_2,
            status=BookingAssignment.Status.PENDING,
        )
        self.client.force_authenticate(user=assignment_2.partner.user)
        self.client.post(f'/api/v1/partner/jobs/assignments/{assignment_2.id}/accept/')
        for step in ('on_the_way', 'arrived', 'in_progress', 'completed'):
            response = self._advance(assignment_2.id, step)
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        payment_2 = Payment.objects.get(booking_id=booking_id_2)
        self.assertEqual(payment_2.status, Payment.Status.PAID)

    def test_unavailable_date_skips_partner_in_auto_assign(self):
        scheduled = timezone.localdate() + timedelta(days=1)
        PartnerUnavailableDate.objects.create(partner=self.partner, date=scheduled)
        booking_id = self._create_and_pay_booking()
        assignment = BookingAssignment.objects.get(booking_id=booking_id)
        self.assertEqual(assignment.partner_id, self.partner_2.id)

        self.client.force_authenticate(user=self.partner_user)
        blocked = self.client.post(
            '/api/v1/partner/unavailable-dates/',
            {'date': (timezone.localdate() + timedelta(days=3)).isoformat()},
            format='json',
        )
        self.assertEqual(blocked.status_code, status.HTTP_201_CREATED)
        listed = self.client.get('/api/v1/partner/unavailable-dates/')
        self.assertEqual(len(listed.data), 2)

    def test_device_token_and_reject_reason(self):
        self.client.force_authenticate(user=self.partner_user)
        token = self.client.post(
            '/api/v1/partner/me/device-token/',
            {'token': 'local-test-token', 'platform': 'android'},
            format='json',
        )
        self.assertEqual(token.status_code, status.HTTP_201_CREATED)

        booking_id = self._create_and_pay_booking()
        assignment = BookingAssignment.objects.get(booking_id=booking_id, partner=self.partner)
        self.client.force_authenticate(user=self.partner_user)
        reject = self.client.post(
            f'/api/v1/partner/jobs/assignments/{assignment.id}/reject/',
            {'reason': 'Too far'},
            format='json',
        )
        self.assertEqual(reject.status_code, status.HTTP_200_OK)
        assignment.refresh_from_db()
        self.assertEqual(assignment.rejection_reason, 'Too far')
        rejected_jobs = self.client.get('/api/v1/partner/jobs/', {'status': 'rejected'})
        self.assertEqual(len(rejected_jobs.data), 1)
