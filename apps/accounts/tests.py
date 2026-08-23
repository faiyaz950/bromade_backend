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
