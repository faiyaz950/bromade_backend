from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import User
from apps.bookings.models import Booking, BookingItem, BookingStatusLog
from apps.catalog.models import Category, CityPackagePrice, Service, ServicePackage
from apps.customers.models import CustomerProfile
from apps.locations.models import Address, City
from apps.partners.models import PartnerCity, PartnerProfile, PartnerService


# Curated local media images served by Django
IMAGES = {
    'cleaning_cat': '/media/catalog/cleaning.jpg',
    'repairs_cat': '/media/catalog/repairs.jpg',
    'other_cat': '/media/catalog/other.jpg',
    'bathroom': '/media/catalog/bathroom.jpg',
    'kitchen': '/media/catalog/kitchen.jpg',
    'full_house': '/media/catalog/full_house.jpg',
    'sofa': '/media/catalog/sofa.jpg',
    'carpet': '/media/catalog/carpet.jpg',
    'tank': '/media/catalog/tank.jpg',
    'ac': '/media/catalog/ac.jpg',
    'plumber': '/media/catalog/plumber.jpg',
    'electrician': '/media/catalog/electrician.jpg',
    'ro': '/media/catalog/ro.jpg',
    'washer': '/media/catalog/washer.jpg',
    'pest': '/media/catalog/pest.jpg',
    'painting': '/media/catalog/painting.jpg',
    'office': '/media/catalog/office.jpg',
}

class Command(BaseCommand):
    help = 'Seed rich example data with service images for Booking MVP.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Re-seed even if catalog data already exists.',
        )

    def handle(self, *args, **options):
        if Category.objects.exists() and not options['force']:
            self.stdout.write(self.style.WARNING(
                'Catalog already present; skipping seed. Use --force to re-seed.'
            ))
            return

        cities = self._seed_cities()
        packages = self._seed_catalog(cities)
        demo_user, addresses = self._seed_demo_customer(cities[0])
        self._seed_demo_partners(cities[0], packages)
        self._seed_demo_bookings(demo_user, addresses[0], packages)

        self.stdout.write(self.style.SUCCESS('Example app data with images seeded successfully.'))
        self.stdout.write(self.style.WARNING('Demo customer phone for OTP login: +919876543210'))
        self.stdout.write(self.style.WARNING('Demo partner phones: +919888888801 (Ravi), +919888888802 (Anita)'))

    def _seed_cities(self):
        city_defs = [
            ('Bengaluru', 'bengaluru', 'Karnataka'),
            ('Mumbai', 'mumbai', 'Maharashtra'),
            ('Delhi', 'delhi', 'Delhi'),
            ('Hyderabad', 'hyderabad', 'Telangana'),
            ('Pune', 'pune', 'Maharashtra'),
        ]
        cities = []
        for name, slug, state in city_defs:
            city, _ = City.objects.get_or_create(
                slug=slug,
                defaults={'name': name, 'state': state, 'is_active': True},
            )
            cities.append(city)
        return cities

    def _seed_catalog(self, cities):
        seed = {
            'Cleaning': {
                'image': IMAGES['cleaning_cat'],
                'services': [
                    ('Bathroom Cleaning', 'Deep clean for bathrooms, tiles, and fixtures.', IMAGES['bathroom'], [
                        ('Classic Bathroom Clean', 1499, 1299, 90),
                        ('Premium Bathroom Spa', 2199, 1899, 120),
                    ]),
                    ('Kitchen Cleaning', 'Degreasing and deep cleaning for kitchens.', IMAGES['kitchen'], [
                        ('Kitchen Revival', 1799, 1549, 100),
                        ('Kitchen Deep Clean Plus', 2499, 2199, 140),
                    ]),
                    ('Full House Cleaning', 'Complete home cleaning for living spaces.', IMAGES['full_house'], [
                        ('1 BHK Full Clean', 2499, 2199, 150),
                        ('2 BHK Full Clean', 3499, 2999, 210),
                        ('3 BHK Full Clean', 4499, 3899, 270),
                    ]),
                    ('Sofa Cleaning', 'Fabric and leather sofa shampooing.', IMAGES['sofa'], [
                        ('3 Seater Sofa Clean', 999, 849, 75),
                    ]),
                    ('Carpet Cleaning', 'Deep carpet shampoo and dry.', IMAGES['carpet'], [
                        ('Carpet Clean (upto 50 sq ft)', 799, 699, 60),
                    ]),
                    ('Water Tank Cleaning', 'Safe tank cleaning with disinfection.', IMAGES['tank'], [
                        ('Overhead Tank Clean', 1299, 1099, 90),
                    ]),
                ],
            },
            'Home Repairs': {
                'image': IMAGES['repairs_cat'],
                'services': [
                    ('AC Service', 'Routine AC servicing and inspection.', IMAGES['ac'], [
                        ('Split AC Service', 699, 599, 60),
                        ('Window AC Service', 599, 499, 50),
                    ]),
                    ('Plumber', 'Repairs for taps, leaks, and fittings.', IMAGES['plumber'], [
                        ('Plumbing Visit', 399, 349, 45),
                        ('Leak Fix Package', 799, 699, 70),
                    ]),
                    ('Electrician', 'Switchboards, wiring checks, and fittings.', IMAGES['electrician'], [
                        ('Electrician Visit', 399, 349, 45),
                        ('Switchboard Repair', 699, 599, 60),
                    ]),
                    ('RO Service', 'RO filter check and basic maintenance.', IMAGES['ro'], [
                        ('RO Basic Service', 499, 449, 50),
                    ]),
                    ('Washing Machine Repair', 'Diagnosis and repair for washing machines.', IMAGES['washer'], [
                        ('Washer Inspection Visit', 449, 399, 50),
                    ]),
                ],
            },
            'Other Services': {
                'image': IMAGES['other_cat'],
                'services': [
                    ('Pest Control', 'Cockroach and general pest treatment.', IMAGES['pest'], [
                        ('1 BHK Pest Control', 999, 899, 60),
                        ('2 BHK Pest Control', 1299, 1149, 75),
                    ]),
                    ('Painting', 'Interior touch-up and wall painting estimate visit.', IMAGES['painting'], [
                        ('Painting Consultation Visit', 299, 249, 40),
                    ]),
                    ('Office Cleaning', 'Commercial workspace cleaning packages.', IMAGES['office'], [
                        ('Small Office Clean', 2999, 2699, 180),
                    ]),
                ],
            },
        }

        all_packages = []
        for index, (category_name, payload) in enumerate(seed.items(), start=1):
            category, _ = Category.objects.update_or_create(
                name=category_name,
                defaults={
                    'description': f'{category_name} for homes and workplaces',
                    'image_url': payload['image'],
                    'sort_order': index,
                    'is_active': True,
                },
            )
            for service_name, description, image_url, packages in payload['services']:
                service, _ = Service.objects.update_or_create(
                    category=category,
                    name=service_name,
                    defaults={
                        'short_description': description,
                        'description': description,
                        'image_url': image_url,
                        'duration_minutes': packages[0][3],
                        'is_active': True,
                    },
                )
                for package_name, base_price, discounted_price, duration in packages:
                    package, _ = ServicePackage.objects.update_or_create(
                        service=service,
                        name=package_name,
                        defaults={
                            'description': f'{package_name}: professional {service_name.lower()} by Brolytics.',
                            'image_url': image_url,
                            'base_price': Decimal(base_price),
                            'discounted_price': Decimal(discounted_price),
                            'duration_minutes': duration,
                            'is_active': True,
                        },
                    )
                    all_packages.append(package)
                    for city in cities:
                        CityPackagePrice.objects.update_or_create(
                            city=city,
                            package=package,
                            defaults={
                                'price': Decimal(base_price),
                                'discounted_price': Decimal(discounted_price),
                                'is_active': True,
                            },
                        )
        return all_packages

    def _seed_demo_customer(self, city):
        user, created = User.objects.get_or_create(
            phone_number='+919876543210',
            defaults={'first_name': 'Priya', 'last_name': 'Sharma', 'is_active': True},
        )
        if created:
            user.set_unusable_password()
            user.save()

        CustomerProfile.objects.update_or_create(
            user=user,
            defaults={'full_name': 'Priya Sharma', 'email': 'priya.demo@brolytics.test'},
        )

        home, _ = Address.objects.update_or_create(
            user=user,
            label='Home',
            defaults={
                'city': city,
                'contact_name': 'Priya Sharma',
                'contact_phone': '+919876543210',
                'line1': '12, Prestige Lakeside Apts',
                'line2': 'Whitefield',
                'landmark': 'Near Forum Shantiniketan',
                'pincode': '560066',
                'latitude': Decimal('12.969800'),
                'longitude': Decimal('77.750000'),
                'is_default': True,
            },
        )
        office, _ = Address.objects.update_or_create(
            user=user,
            label='Office',
            defaults={
                'city': city,
                'contact_name': 'Priya Sharma',
                'contact_phone': '+919876543210',
                'line1': 'Brolytics Hub, 4th Floor',
                'line2': 'Indiranagar 100 Feet Road',
                'landmark': 'Opposite metro station',
                'pincode': '560038',
                'latitude': Decimal('12.978400'),
                'longitude': Decimal('77.640800'),
                'is_default': False,
            },
        )
        return user, [home, office]

    def _seed_demo_partners(self, city, packages):
        bathroom = next((p for p in packages if 'Bathroom' in p.service.name), None)
        ac = next((p for p in packages if 'Split AC' in p.name), None)
        if bathroom is None or ac is None:
            return

        partner_defs = [
            ('+919888888801', 'Ravi Kumar', [bathroom.service, ac.service]),
            ('+919888888802', 'Anita Desai', [bathroom.service, ac.service]),
        ]
        for phone, name, services in partner_defs:
            user, created = User.objects.get_or_create(
                phone_number=phone,
                defaults={'first_name': name.split()[0], 'last_name': name.split()[-1], 'is_active': True},
            )
            if created:
                user.set_unusable_password()
                user.save()

            profile, _ = PartnerProfile.objects.update_or_create(
                user=user,
                defaults={
                    'full_name': name,
                    'is_active': True,
                    'is_available_for_assignment': True,
                    'approval_status': PartnerProfile.ApprovalStatus.APPROVED,
                },
            )
            PartnerCity.objects.get_or_create(partner=profile, city=city)
            for service in services:
                PartnerService.objects.get_or_create(partner=profile, service=service)

    def _seed_demo_bookings(self, user, address, packages):
        if not packages:
            return

        bathroom = next((p for p in packages if 'Bathroom' in p.name), packages[0])
        ac = next((p for p in packages if 'Split AC' in p.name), packages[0])

        samples = [
            (bathroom, Booking.Status.CONFIRMED, 1),
            (ac, Booking.Status.PENDING_PAYMENT, 2),
        ]

        for package, status, day_offset in samples:
            scheduled_date = timezone.localdate() + timedelta(days=day_offset)
            booking, created = Booking.objects.get_or_create(
                customer=user,
                address=address,
                city=address.city,
                scheduled_date=scheduled_date,
                scheduled_time='10:00:00',
                defaults={
                    'status': status,
                    'subtotal_amount': package.discounted_price,
                    'total_amount': package.discounted_price,
                    'notes': 'Demo booking for app preview',
                },
            )
            if not created:
                continue

            BookingItem.objects.create(
                booking=booking,
                package=package,
                service_name=package.service.name,
                package_name=package.name,
                unit_price=package.discounted_price,
                quantity=1,
                line_total=package.discounted_price,
            )
            BookingStatusLog.objects.create(
                booking=booking,
                from_status='',
                to_status=status,
                note='Seeded demo booking',
            )
