from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.catalog.models import Category, HomeHeroSlide, Service, ServiceInclusion, ServicePackage, ServiceProcessStep


def _png_upload(name='service.png'):
    from PIL import Image

    buffer = BytesIO()
    Image.new('RGB', (12, 12), color='#F07820').save(buffer, format='PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


class CatalogAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone_number='+919111111111')
        self.client.force_authenticate(user=self.user)
        category = Category.objects.create(name='Cleaning', description='Cleaning services')
        self.service = Service.objects.create(
            category=category,
            name='Bathroom Cleaning',
            headline='A Cleaner Bathroom, Every Day',
            short_description='Deep clean',
            description=(
                'Keep your bathroom fresh, clean and guest-ready with regular bathroom cleaning. '
                'Our professionals clean key surfaces including the WC, washbasin, tiles and fittings, '
                'helping maintain cleanliness and everyday hygiene.'
            ),
        )
        ServiceInclusion.objects.create(
            service=self.service,
            kind=ServiceInclusion.Kind.INCLUDED,
            text='Cleaning of toilet bowl (inside and rim)',
            sort_order=0,
        )
        ServiceInclusion.objects.create(
            service=self.service,
            kind=ServiceInclusion.Kind.EXCLUDED,
            text='Deep cleaning such as tile grout scrubbing',
            sort_order=0,
        )
        ServiceProcessStep.objects.create(
            service=self.service,
            title='Toilet cleaning',
            description='The toilet bowl is cleaned as the initial step of the process',
            sort_order=0,
        )
        self.package = ServicePackage.objects.create(
            service=self.service,
            name='Classic Bathroom Clean',
            description='Package',
            base_price=1200,
            discounted_price=999,
        )

    def test_list_categories_and_package_detail(self):
        categories_response = self.client.get('/api/v1/catalog/categories/')
        self.assertEqual(categories_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(categories_response.data), 1)
        service_payload = categories_response.data[0]['services'][0]
        self.assertEqual(service_payload['headline'], 'A Cleaner Bathroom, Every Day')
        self.assertEqual(
            service_payload['included_items'],
            ['Cleaning of toilet bowl (inside and rim)'],
        )
        self.assertEqual(
            service_payload['excluded_items'],
            ['Deep cleaning such as tile grout scrubbing'],
        )
        self.assertEqual(service_payload['process_steps'][0]['title'], 'Toilet cleaning')

        package_response = self.client.get(f'/api/v1/catalog/packages/{self.package.id}/')
        self.assertEqual(package_response.status_code, status.HTTP_200_OK)
        self.assertEqual(package_response.data['name'], 'Classic Bathroom Clean')

    def test_home_slides_list_active_in_order(self):
        HomeHeroSlide.objects.create(
            title='Later',
            image_url='https://cdn.example.com/later.jpg',
            sort_order=2,
        )
        HomeHeroSlide.objects.create(
            title='First',
            image_url='https://cdn.example.com/first.jpg',
            sort_order=0,
        )
        HomeHeroSlide.objects.create(
            title='Hidden',
            image_url='https://cdn.example.com/hidden.jpg',
            sort_order=1,
            is_active=False,
        )

        response = self.client.get('/api/v1/catalog/home-slides/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([slide['title'] for slide in response.data], ['First', 'Later'])
        self.assertEqual(response.data[0]['image_url'], 'https://cdn.example.com/first.jpg')

    def test_service_uploaded_image_is_returned_by_api(self):
        self.service.image.save('bathroom.png', _png_upload('bathroom.png'), save=True)

        response = self.client.get('/api/v1/catalog/categories/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        image_url = response.data[0]['services'][0]['image_url']
        self.assertIn('/media/catalog/services/', image_url)
        self.assertTrue(image_url.endswith('.png'))
