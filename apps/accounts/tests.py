from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase


class AuthAPITests(APITestCase):
    def test_request_and_verify_otp(self):
        request_response = self.client.post('/api/v1/auth/otp/request/', {'phone_number': '+919876543210'}, format='json')
        self.assertEqual(request_response.status_code, status.HTTP_201_CREATED)
        code = request_response.data['otp_code']

        verify_response = self.client.post(
            '/api/v1/auth/otp/verify/',
            {'phone_number': '+919876543210', 'code': code, 'first_name': 'Bro', 'last_name': 'User'},
            format='json',
        )
        self.assertEqual(verify_response.status_code, status.HTTP_200_OK)
        self.assertIn('access', verify_response.data)

    @patch('apps.accounts.serializers.verify_id_token')
    def test_firebase_login_issues_jwt(self, mock_verify):
        mock_verify.return_value = {'phone_number': '+919900001111'}
        response = self.client.post(
            '/api/v1/auth/firebase/',
            {
                'id_token': 'fake-token',
                'first_name': 'Asha',
                'last_name': 'Khan',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertEqual(response.data['user']['phone_number'], '+919900001111')

    @patch('apps.accounts.serializers.verify_id_token')
    def test_firebase_google_login_issues_jwt(self, mock_verify):
        mock_verify.return_value = {
            'email': 'asha@gmail.com',
            'name': 'Asha Khan',
            'user_id': 'google-uid-1',
            'sub': 'google-uid-1',
            'firebase': {'sign_in_provider': 'google.com'},
        }
        response = self.client.post(
            '/api/v1/auth/firebase/',
            {'id_token': 'fake-google-token'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertEqual(response.data['user']['email'], 'asha@gmail.com')
        self.assertIsNone(response.data['user']['phone_number'])
        self.assertEqual(response.data['user']['full_name'], 'Asha Khan')

        again = self.client.post(
            '/api/v1/auth/firebase/',
            {'id_token': 'fake-google-token'},
            format='json',
        )
        self.assertEqual(again.status_code, status.HTTP_200_OK)
        self.assertEqual(again.data['user']['id'], response.data['user']['id'])
        self.assertFalse(again.data['is_new_user'])

    def test_update_name_after_login(self):
        request_response = self.client.post(
            '/api/v1/auth/otp/request/',
            {'phone_number': '+919111111112'},
            format='json',
        )
        code = request_response.data['otp_code']
        verify_response = self.client.post(
            '/api/v1/auth/otp/verify/',
            {'phone_number': '+919111111112', 'code': code},
            format='json',
        )
        self.assertEqual(verify_response.data['user']['full_name'], '')
        token = verify_response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        me_response = self.client.patch(
            '/api/v1/auth/me/',
            {'first_name': 'Faiyaz', 'last_name': 'Mujtaba'},
            format='json',
        )
        self.assertEqual(me_response.status_code, status.HTTP_200_OK)
        self.assertEqual(me_response.data['full_name'], 'Faiyaz Mujtaba')

    @patch('apps.accounts.serializers.verify_id_token')
    def test_google_user_can_add_name_and_phone(self, mock_verify):
        mock_verify.return_value = {
            'email': 'new.user@gmail.com',
            'name': 'New User',
            'user_id': 'google-uid-2',
            'sub': 'google-uid-2',
            'firebase': {'sign_in_provider': 'google.com'},
        }
        login = self.client.post(
            '/api/v1/auth/firebase/',
            {'id_token': 'fake-google-token'},
            format='json',
        )
        self.assertTrue(login.data['is_new_user'])
        self.assertIsNone(login.data['user']['phone_number'])
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {login.data["access"]}')
        me_response = self.client.patch(
            '/api/v1/auth/me/',
            {
                'first_name': 'Faiyaz',
                'last_name': 'Mujtaba',
                'phone_number': '8340715516',
            },
            format='json',
        )
        self.assertEqual(me_response.status_code, status.HTTP_200_OK)
        self.assertEqual(me_response.data['full_name'], 'Faiyaz Mujtaba')
        self.assertEqual(me_response.data['phone_number'], '+918340715516')

    def test_refresh_token_issues_new_access_token(self):
        request_response = self.client.post(
            '/api/v1/auth/otp/request/',
            {'phone_number': '+919222222221'},
            format='json',
        )
        verify_response = self.client.post(
            '/api/v1/auth/otp/verify/',
            {
                'phone_number': '+919222222221',
                'code': request_response.data['otp_code'],
                'first_name': 'Ravi',
                'last_name': 'Kumar',
            },
            format='json',
        )
        refresh = verify_response.data['refresh']
        refreshed = self.client.post('/api/v1/auth/token/refresh/', {'refresh': refresh}, format='json')
        self.assertEqual(refreshed.status_code, status.HTTP_200_OK)
        self.assertIn('access', refreshed.data)

    def test_email_register_and_login(self):
        register = self.client.post(
            '/api/v1/auth/register/',
            {
                'email': 'customer@example.com',
                'password': 'secretpass',
                'phone_number': '9876543210',
                'first_name': 'Bro',
                'last_name': 'User',
            },
            format='json',
        )
        self.assertEqual(register.status_code, status.HTTP_201_CREATED)
        self.assertIn('access', register.data)
        self.assertTrue(register.data['is_new_user'])
        self.assertEqual(register.data['user']['email'], 'customer@example.com')
        self.assertEqual(register.data['user']['phone_number'], '+919876543210')
        self.assertEqual(register.data['user']['full_name'], 'Bro User')

        login = self.client.post(
            '/api/v1/auth/login/',
            {'identifier': 'customer@example.com', 'password': 'secretpass'},
            format='json',
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.assertFalse(login.data['is_new_user'])
        self.assertEqual(login.data['user']['id'], register.data['user']['id'])

        phone_login = self.client.post(
            '/api/v1/auth/login/',
            {'identifier': '9876543210', 'password': 'secretpass'},
            format='json',
        )
        self.assertEqual(phone_login.status_code, status.HTTP_200_OK)
        self.assertEqual(phone_login.data['user']['id'], register.data['user']['id'])

        bad = self.client.post(
            '/api/v1/auth/login/',
            {'identifier': 'customer@example.com', 'password': 'wrongpass'},
            format='json',
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

    def test_phone_register_without_email(self):
        register = self.client.post(
            '/api/v1/auth/register/',
            {
                'phone_number': '9123456780',
                'password': 'secretpass',
                'first_name': 'Phone',
                'last_name': 'Only',
            },
            format='json',
        )
        self.assertEqual(register.status_code, status.HTTP_201_CREATED, register.data)
        self.assertEqual(register.data['user']['phone_number'], '+919123456780')
        self.assertEqual(register.data['user']['email'], None)

        login = self.client.post(
            '/api/v1/auth/login/',
            {'identifier': '9123456780', 'password': 'secretpass'},
            format='json',
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.assertEqual(login.data['user']['id'], register.data['user']['id'])

    def test_register_without_phone_is_rejected(self):
        register = self.client.post(
            '/api/v1/auth/register/',
            {'email': 'nophoneuser@example.com', 'password': 'secretpass'},
            format='json',
        )
        self.assertEqual(register.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('apps.accounts.serializers.verify_id_token')
    def test_google_account_cannot_login_with_password(self, mock_verify):
        mock_verify.return_value = {
            'email': 'google.only@gmail.com',
            'name': 'Google User',
            'user_id': 'google-uid-pw',
            'sub': 'google-uid-pw',
        }
        self.client.post(
            '/api/v1/auth/firebase/',
            {'id_token': 'fake-google-token'},
            format='json',
        )
        login = self.client.post(
            '/api/v1/auth/login/',
            {'identifier': 'google.only@gmail.com', 'password': 'anything123'},
            format='json',
        )
        self.assertEqual(login.status_code, status.HTTP_400_BAD_REQUEST)


class DeleteAccountTests(APITestCase):
    def setUp(self):
        from datetime import date, time

        from apps.accounts.models import User, UserDeviceToken
        from apps.bookings.models import Booking
        from apps.locations.models import Address, City

        self.user = User.objects.create_user(
            phone_number='+919811112222',
            email='asha@example.com',
            google_id='google-123',
            first_name='Asha',
        )
        UserDeviceToken.objects.create(user=self.user, token='push-token', platform='android')
        city, _ = City.objects.get_or_create(slug='patna', defaults={'name': 'Patna', 'state': 'Bihar'})
        self.booked_address = Address.objects.create(
            user=self.user, city=city, label='Home', contact_name='Asha', contact_phone='+919811112222',
            line1='Flat 2, Boring Road', pincode='800001', latitude=25.6, longitude=85.1,
        )
        self.spare_address = Address.objects.create(
            user=self.user, city=city, label='Office', contact_name='Asha', contact_phone='+919811112222',
            line1='Office 9', pincode='800002',
        )
        self.booking = Booking.objects.create(
            customer=self.user, address=self.booked_address, city=city,
            scheduled_date=date(2026, 1, 1), scheduled_time=time(10, 0),
            subtotal_amount=500, total_amount=500,
            status=Booking.Status.COMPLETED, notes='Gate code 4455',
        )
        self.client.force_authenticate(user=self.user)

    def test_delete_erases_personal_data_and_keeps_booking(self):
        from apps.accounts.models import UserDeviceToken
        from apps.locations.models import Address

        response = self.client.delete('/api/v1/auth/me/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertIsNone(self.user.phone_number)
        self.assertIsNone(self.user.email)
        self.assertIsNone(self.user.google_id)
        self.assertEqual(self.user.first_name, '')
        self.assertFalse(UserDeviceToken.objects.filter(user=self.user).exists())
        self.assertFalse(Address.objects.filter(pk=self.spare_address.pk).exists())

        self.booked_address.refresh_from_db()
        self.assertEqual(self.booked_address.contact_phone, '')
        self.assertIsNone(self.booked_address.latitude)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.notes, '')

    def test_upcoming_booking_blocks_deletion(self):
        from apps.bookings.models import Booking

        self.booking.status = Booking.Status.CONFIRMED
        self.booking.save()
        response = self.client.delete('/api/v1/auth/me/')
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_tokens_stop_working_after_deletion(self):
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(self.user)
        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        self.assertEqual(self.client.delete('/api/v1/auth/me/').status_code, status.HTTP_204_NO_CONTENT)

        self.assertEqual(self.client.get('/api/v1/auth/me/').status_code, status.HTTP_401_UNAUTHORIZED)
        refreshed = self.client.post('/api/v1/auth/token/refresh/', {'refresh': str(refresh)}, format='json')
        self.assertEqual(refreshed.status_code, status.HTTP_401_UNAUTHORIZED)
