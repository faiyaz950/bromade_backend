from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.catalog.models import (
    Category,
    HomeHeroSlide,
    PackageInclusion,
    Service,
    ServiceInclusion,
    ServicePackage,
    ServiceProcessStep,
)


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

    def test_services_carry_real_ratings_and_recent_bookings(self):
        from apps.bookings.models import Booking, BookingItem, BookingRating
        from apps.locations.models import Address, City

        city, _ = City.objects.get_or_create(slug='patna', defaults={'name': 'Patna', 'state': 'Bihar'})
        address = Address.objects.create(
            user=self.user, city=city, label='Home', contact_name='A',
            contact_phone='+919111111111', line1='Road', pincode='800001',
        )

        def book(status_, stars=None, items=1):
            booking = Booking.objects.create(
                customer=self.user, address=address, city=city, status=status_,
                scheduled_date='2026-10-10', scheduled_time='10:00',
                subtotal_amount=999, total_amount=999,
            )
            for _ in range(items):
                BookingItem.objects.create(
                    booking=booking, package=self.package, service_name='Bathroom Cleaning',
                    package_name='Classic', unit_price=999, line_total=999,
                )
            if stars:
                BookingRating.objects.create(booking=booking, stars=stars)

        book(Booking.Status.COMPLETED, stars=5, items=2)
        book(Booking.Status.COMPLETED, stars=4)
        book(Booking.Status.CONFIRMED)
        book(Booking.Status.CANCELLED)

        service = self.client.get('/api/v1/catalog/categories/').data[0]['services'][0]
        self.assertEqual(service['rating_count'], 2)
        self.assertEqual(service['rating_average'], 4.5)
        self.assertEqual(service['recent_bookings'], 3)

    def test_unrated_service_has_no_average(self):
        service = self.client.get('/api/v1/catalog/categories/').data[0]['services'][0]
        self.assertIsNone(service['rating_average'])
        self.assertEqual(service['rating_count'], 0)
        self.assertEqual(service['recent_bookings'], 0)

    def test_each_package_has_its_own_includes(self):
        premium = ServicePackage.objects.create(
            service=self.service,
            name='Premium Bathroom Spa',
            description='Package',
            base_price=2200,
            discounted_price=1899,
        )
        PackageInclusion.objects.create(package=premium, kind='included', text='Hard water stain removal')
        PackageInclusion.objects.create(package=premium, kind='excluded', text='Plumbing repairs')

        response = self.client.get('/api/v1/catalog/categories/')
        packages = {p['name']: p for p in response.data[0]['services'][0]['packages']}
        self.assertEqual(packages['Premium Bathroom Spa']['included_items'], ['Hard water stain removal'])
        self.assertEqual(packages['Premium Bathroom Spa']['excluded_items'], ['Plumbing repairs'])
        self.assertEqual(packages['Classic Bathroom Clean']['included_items'], [])

        detail = self.client.get(f'/api/v1/catalog/packages/{premium.id}/')
        self.assertEqual(detail.data['included_items'], ['Hard water stain removal'])

    def test_seed_package_details_keeps_admin_edits(self):
        from apps.catalog.package_details import seed_package_details

        PackageInclusion.objects.create(package=self.package, kind='included', text='Custom admin row')
        seed_package_details()
        self.assertEqual(list(self.package.inclusions.values_list('text', flat=True)), ['Custom admin row'])
        self.package.refresh_from_db()
        self.assertEqual(self.package.description, 'Package')

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
