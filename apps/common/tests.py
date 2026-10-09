from datetime import timedelta
from unittest import mock

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.common.push import DeliveryReport


class LegalPagesTests(TestCase):
    def test_legal_pages_are_public(self):
        for url, heading in (
            ('/privacy/', 'Privacy Policy'),
            ('/terms/', 'Terms &amp; Conditions'),
            ('/delete-account/', 'Delete your account'),
        ):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertContains(response, heading)


class AppReleaseTests(TestCase):
    def test_returns_versions_for_platform(self):
        from apps.common.models import AppRelease

        AppRelease.objects.create(
            platform='android',
            latest_version='1.4.0',
            min_supported_version='1.2.0',
            store_url='https://play.google.com/store/apps/details?id=com.brolytics.customer_app',
        )
        data = self.client.get('/api/v1/app-release/', {'app': 'customer', 'platform': 'android'}).json()
        self.assertEqual(data['latest_version'], '1.4.0')
        self.assertEqual(data['min_supported_version'], '1.2.0')

    def test_unconfigured_platform_returns_nulls(self):
        data = self.client.get('/api/v1/app-release/', {'platform': 'ios'}).json()
        self.assertIsNone(data['latest_version'])
        self.assertIsNone(data['min_supported_version'])


class PushCampaignTests(TestCase):
    def setUp(self):
        from apps.accounts.models import User, UserDeviceToken
        from apps.locations.models import Address, City
        from apps.partners.models import PartnerCity, PartnerDeviceToken, PartnerProfile

        self.patna, _ = City.objects.get_or_create(slug='patna', defaults={'name': 'Patna', 'state': 'Bihar'})
        self.pune = City.objects.create(name='Pune', slug='pune', state='Maharashtra')

        self.ravi = User.objects.create_user(phone_number='+919111111111', email='ravi@example.com')
        UserDeviceToken.objects.create(user=self.ravi, token='ravi-phone')
        Address.objects.create(
            user=self.ravi, city=self.patna, label='Home', contact_name='Ravi',
            contact_phone='+919111111111', line1='Boring Road', pincode='800001',
        )
        self.asha = User.objects.create_user(phone_number='+919222222222')
        UserDeviceToken.objects.create(user=self.asha, token='asha-phone')
        Address.objects.create(
            user=self.asha, city=self.pune, label='Home', contact_name='Asha',
            contact_phone='+919222222222', line1='Baner', pincode='411045',
        )
        gone = User.objects.create_user(phone_number='+919333333333', is_active=False)
        UserDeviceToken.objects.create(user=gone, token='deleted-account-phone')

        pro_user = User.objects.create_user(phone_number='+919444444444')
        self.pro = PartnerProfile.objects.create(
            user=pro_user, full_name='Sunil', approval_status=PartnerProfile.ApprovalStatus.APPROVED
        )
        PartnerCity.objects.create(partner=self.pro, city=self.patna)
        PartnerDeviceToken.objects.create(partner=self.pro, token='sunil-phone')
        rejected_user = User.objects.create_user(phone_number='+919555555555')
        rejected = PartnerProfile.objects.create(
            user=rejected_user, full_name='X', approval_status=PartnerProfile.ApprovalStatus.REJECTED
        )
        PartnerDeviceToken.objects.create(partner=rejected, token='rejected-phone')

    def campaign(self, **fields):
        from apps.common.models import PushCampaign

        return PushCampaign(title='Hello', body='Big savings', **fields)

    def tokens(self, **fields):
        from apps.common.campaigns import campaign_tokens

        return sorted(campaign_tokens(self.campaign(**fields)))

    def test_audiences(self):
        self.assertEqual(self.tokens(), ['asha-phone', 'ravi-phone'])
        self.assertEqual(self.tokens(target='city', city=self.patna), ['ravi-phone'])
        self.assertEqual(self.tokens(audience='partners'), ['sunil-phone'])
        self.assertEqual(self.tokens(audience='partners', target='city', city=self.pune), [])
        self.assertEqual(self.tokens(target='person', recipient='91111 11111'), ['ravi-phone'])
        self.assertEqual(self.tokens(target='person', recipient='RAVI@example.com'), ['ravi-phone'])
        self.assertEqual(self.tokens(audience='partners', target='person', recipient='9444444444'), ['sunil-phone'])

    def test_validation(self):
        with self.assertRaises(ValidationError) as caught:
            self.campaign(target='person', recipient='9000000000').full_clean()
        self.assertIn('recipient', caught.exception.message_dict)

        with self.assertRaises(ValidationError) as caught:
            self.campaign(target='city', screen='service').full_clean()
        self.assertEqual(set(caught.exception.message_dict), {'city', 'service'})

        with self.assertRaises(ValidationError) as caught:
            self.campaign(send_at=timezone.now() - timedelta(hours=1)).full_clean()
        self.assertIn('send_at', caught.exception.message_dict)

        partners = self.campaign(audience='partners', screen='refer', city=self.pune)
        partners.full_clean()
        self.assertEqual(partners.screen, 'home')
        self.assertIsNone(partners.city)

    @mock.patch('apps.common.campaigns.push_enabled', return_value=True)
    @mock.patch('apps.common.campaigns.deliver_now', return_value=DeliveryReport(delivered=1, expired=1))
    def test_delivers_once_when_due(self, deliver, _enabled):
        from apps.common.campaigns import deliver_campaign, send_due_campaigns

        later = self.campaign(send_at=timezone.now() + timedelta(hours=2))
        later.save()
        due = self.campaign(screen='refer', send_at=timezone.now())
        due.save()

        self.assertEqual(send_due_campaigns(), 1)
        self.assertFalse(deliver_campaign(due.pk))
        deliver.assert_called_once()
        tokens, title, body, data = deliver.call_args.args
        self.assertEqual(sorted(tokens), ['asha-phone', 'ravi-phone'])
        self.assertEqual(data['screen'], 'refer')

        due.refresh_from_db()
        later.refresh_from_db()
        self.assertEqual((due.status, due.devices, due.delivered, due.failed), ('sent', 2, 1, 1))
        self.assertEqual(later.status, 'scheduled')

    def test_admin_pages_render(self):
        from apps.accounts.models import User

        admin_user = User.objects.create_superuser('+919666666666', password='x')
        self.client.force_login(admin_user)
        self.assertEqual(self.client.get('/admin/common/pushcampaign/add/').status_code, 200)
        sent = self.campaign(send_at=timezone.now(), status='sent', devices=2, delivered=2)
        sent.save()
        self.assertEqual(self.client.get('/admin/common/pushcampaign/').status_code, 200)
        self.assertEqual(self.client.get(f'/admin/common/pushcampaign/{sent.pk}/change/').status_code, 200)

    @mock.patch('apps.common.campaigns.push_enabled', return_value=False)
    def test_records_failure_when_push_is_off(self, _enabled):
        from apps.common.campaigns import deliver_campaign

        campaign = self.campaign(send_at=timezone.now())
        campaign.save()
        deliver_campaign(campaign.pk)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, 'failed')
        self.assertIn('Firebase', campaign.error)
