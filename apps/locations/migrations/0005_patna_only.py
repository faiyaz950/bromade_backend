from django.db import migrations


def patna_only(apps, schema_editor):
    City = apps.get_model('locations', 'City')
    patna, _ = City.objects.update_or_create(
        slug='patna',
        defaults={
            'name': 'Patna',
            'state': 'Bihar',
            'is_active': True,
            'aliases': 'Patliputra, Danapur, Phulwari Sharif, Khagaul, Patna Sadar',
            'latitude': 25.5941,
            'longitude': 85.1376,
            'service_radius_km': 30,
        },
    )
    City.objects.exclude(pk=patna.pk).update(is_active=False)


class Migration(migrations.Migration):
    dependencies = [
        ('locations', '0004_alter_city_coming_soon_message'),
    ]

    operations = [migrations.RunPython(patna_only, migrations.RunPython.noop)]
