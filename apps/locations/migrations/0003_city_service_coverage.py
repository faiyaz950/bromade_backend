from django.db import migrations, models


KNOWN_CITIES = {
    'bengaluru': {
        'aliases': 'Bangalore, Bengaluru Urban',
        'latitude': 12.9716,
        'longitude': 77.5946,
        'service_radius_km': 45,
    },
    'mumbai': {
        'aliases': 'Bombay, Mumbai City',
        'latitude': 19.0760,
        'longitude': 72.8777,
        'service_radius_km': 45,
    },
    'delhi': {
        'aliases': 'New Delhi, Delhi NCR, NCR',
        'latitude': 28.6139,
        'longitude': 77.2090,
        'service_radius_km': 45,
    },
    'hyderabad': {
        'aliases': 'Secunderabad',
        'latitude': 17.3850,
        'longitude': 78.4867,
        'service_radius_km': 45,
    },
    'pune': {
        'aliases': 'Poona, Pimpri Chinchwad',
        'latitude': 18.5204,
        'longitude': 73.8567,
        'service_radius_km': 45,
    },
}


def seed_known_city_pins(apps, schema_editor):
    City = apps.get_model('locations', 'City')
    for slug, values in KNOWN_CITIES.items():
        City.objects.filter(slug=slug).update(**values)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('locations', '0002_alter_address_options_alter_city_options'),
    ]

    operations = [
        migrations.AlterField(
            model_name='city',
            name='is_active',
            field=models.BooleanField(
                default=True,
                help_text='Turn on to let customers in this city browse and book. Turn off to show Available soon.',
                verbose_name='services live',
            ),
        ),
        migrations.AddField(
            model_name='city',
            name='aliases',
            field=models.CharField(
                blank=True,
                help_text='Comma-separated names used to match GPS (e.g. Bombay, Mumbai City).',
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name='city',
            name='latitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name='city',
            name='longitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name='city',
            name='service_radius_km',
            field=models.PositiveIntegerField(
                default=40,
                help_text='How far around the city pin we treat as this city.',
            ),
        ),
        migrations.AddField(
            model_name='city',
            name='coming_soon_message',
            field=models.CharField(
                blank=True,
                help_text='Optional copy on the Available soon screen. Leave blank for the default message.',
                max_length=220,
            ),
        ),
        migrations.RunPython(seed_known_city_pins, noop),
    ]
