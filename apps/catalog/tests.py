from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.catalog.models import Category, Service, ServicePackage


class CatalogAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone_number='+919111111111')
        self.client.force_authenticate(user=self.user)
        category = Category.objects.create(name='Cleaning', description='Cleaning services')
        service = Service.objects.create(
            category=category,
            name='Bathroom Cleaning',
            short_description='Deep clean',
        )
        self.package = ServicePackage.objects.create(
            service=service,
            name='Classic Bathroom Clean',
            description='Package',
            base_price=1200,
            discounted_price=999,
        )

    def test_list_categories_and_package_detail(self):
        categories_response = self.client.get('/api/v1/catalog/categories/')
        self.assertEqual(categories_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(categories_response.data), 1)

        package_response = self.client.get(f'/api/v1/catalog/packages/{self.package.id}/')
        self.assertEqual(package_response.status_code, status.HTTP_200_OK)
        self.assertEqual(package_response.data['name'], 'Classic Bathroom Clean')
