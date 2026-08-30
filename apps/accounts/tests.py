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
