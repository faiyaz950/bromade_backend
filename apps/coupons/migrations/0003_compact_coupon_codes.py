from django.db import migrations


def compact_coupon_codes(apps, schema_editor):
    Coupon = apps.get_model('coupons', 'Coupon')
    used = set()
    for coupon in Coupon.objects.order_by('created_at'):
        compact = ''.join(ch for ch in (coupon.code or '').upper() if ch.isalnum())
        if not compact or coupon.code == compact:
            used.add(coupon.code)
            continue
        if compact in used or Coupon.objects.filter(code=compact).exclude(pk=coupon.pk).exists():
            continue
        coupon.code = compact
        coupon.save(update_fields=['code'])
        used.add(compact)


class Migration(migrations.Migration):

    dependencies = [
        ('coupons', '0002_coupon_apply_scope_alter_coupon_services'),
    ]

    operations = [
        migrations.RunPython(compact_coupon_codes, migrations.RunPython.noop),
    ]
