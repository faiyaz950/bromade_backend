from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partners', '0003_visit_lifecycle_ratings_partner_ops'),
    ]

    operations = [
        migrations.AddField(
            model_name='partnerprofile',
            name='aadhaar_number',
            field=models.CharField(blank=True, max_length=12),
        ),
        migrations.AddField(
            model_name='partnerprofile',
            name='address_line',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='partnerprofile',
            name='bank_account_holder',
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name='partnerprofile',
            name='bank_account_number',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='partnerprofile',
            name='bank_ifsc',
            field=models.CharField(blank=True, max_length=11),
        ),
        migrations.AddField(
            model_name='partnerprofile',
            name='email',
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name='partnerprofile',
            name='pan_number',
            field=models.CharField(blank=True, max_length=10),
        ),
        migrations.AddField(
            model_name='partnerprofile',
            name='pincode',
            field=models.CharField(blank=True, max_length=6),
        ),
        migrations.AddField(
            model_name='partnerprofile',
            name='upi_id',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='partnerprofile',
            name='upi_phone',
            field=models.CharField(blank=True, max_length=10),
        ),
        migrations.AddField(
            model_name='partnerprofile',
            name='years_experience',
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]
