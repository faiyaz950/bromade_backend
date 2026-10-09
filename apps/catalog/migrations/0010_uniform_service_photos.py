from django.db import migrations

PHOTOS = (
    'ac', 'bathroom', 'carpet', 'electrician', 'full_house', 'kitchen', 'office',
    'painting', 'pest', 'plumber', 'ro', 'sofa', 'washer', 'tank',
)


def _swap(apps, old_prefix, new_prefix):
    Service = apps.get_model('catalog', 'Service')
    for name in PHOTOS:
        # Only rows still on the seeded photo; admin uploads and custom URLs stay.
        Service.objects.filter(image='', image_url=f'{old_prefix}{name}.jpg').update(
            image_url=f'{new_prefix}{name}.jpg'
        )


def forwards(apps, schema_editor):
    _swap(apps, '/media/catalog/real/', '/static/catalog/services/')


def backwards(apps, schema_editor):
    _swap(apps, '/static/catalog/services/', '/media/catalog/real/')


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0009_package_inclusions'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
