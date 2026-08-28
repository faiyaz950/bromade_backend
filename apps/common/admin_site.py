from django.contrib.admin import AdminSite
from django.db.models import Count, Sum
from django.urls import reverse
from django.utils import timezone


class BrolyticsAdminSite(AdminSite):
    site_header = 'Brolytics Operations'
    site_title = 'Brolytics Admin'
    index_title = 'Command Center'
    site_url = '/'
    enable_nav_sidebar = True
    login_template = 'admin/brolytics_login.html'
    index_template = 'admin/brolytics_index.html'

    def each_context(self, request):
        context = super().each_context(request)
        context['brolytics_brand'] = 'Brolytics'
        context['brolytics_tagline'] = 'Home Services'
        return context

    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['dashboard'] = self._dashboard_stats()
        return super().index(request, extra_context)

    def _dashboard_stats(self):
        from apps.bookings.models import Booking, BookingAssignment
        from apps.catalog.models import Category, HomeHeroSlide, Service
        from apps.coupons.models import Coupon
        from apps.customers.models import CustomerProfile
        from apps.locations.models import Address, City
        from apps.partners.models import PartnerProfile
        from apps.payments.models import Payment

        today = timezone.localdate()
        bookings = Booking.objects.all()
        payments = Payment.objects.filter(status=Payment.Status.PAID)
        assignments = BookingAssignment.objects.select_related('partner', 'booking', 'booking__customer', 'booking__city')

        confirmed = bookings.filter(status=Booking.Status.CONFIRMED)
        pending = bookings.filter(status=Booking.Status.PENDING_PAYMENT)
        today_bookings = bookings.filter(scheduled_date=today)

        revenue = payments.aggregate(total=Sum('amount'))['total'] or 0
        today_revenue = payments.filter(created_at__date=today).aggregate(total=Sum('amount'))['total'] or 0

        status_breakdown = list(
            bookings.values('status').annotate(count=Count('id')).order_by('-count')
        )
        assignment_breakdown = list(
            bookings.values('assignment_status').annotate(count=Count('id')).order_by('-count')
        )

        recent = list(
            bookings.select_related('customer', 'city')
            .order_by('-created_at')[:8]
        )
        recent_assignments = list(
            assignments.order_by('-assigned_at')[:8]
        )
        pending_partners = list(
            PartnerProfile.objects.filter(approval_status=PartnerProfile.ApprovalStatus.PENDING)
            .select_related('user')
            .order_by('-created_at')[:6]
        )

        return {
            'cards': [
                {
                    'label': 'Customer orders',
                    'value': bookings.count(),
                    'hint': f'{confirmed.count()} confirmed · {pending.count()} pending payment',
                    'tone': 'forest',
                    'url': reverse('admin:bookings_booking_changelist'),
                },
                {
                    'label': 'Partner jobs',
                    'value': assignments.count(),
                    'hint': f'{assignments.filter(status=BookingAssignment.Status.PENDING).count()} awaiting response',
                    'tone': 'champagne',
                    'url': reverse('admin:bookings_bookingassignment_changelist'),
                },
                {
                    'label': 'Customers',
                    'value': CustomerProfile.objects.count(),
                    'hint': f'{Address.objects.count()} saved addresses',
                    'tone': 'sage',
                    'url': reverse('admin:customers_customerprofile_changelist'),
                },
                {
                    'label': 'Partners',
                    'value': PartnerProfile.objects.filter(approval_status=PartnerProfile.ApprovalStatus.APPROVED).count(),
                    'hint': f'{PartnerProfile.objects.filter(approval_status=PartnerProfile.ApprovalStatus.PENDING).count()} pending approval',
                    'tone': 'ink',
                    'url': reverse('admin:partners_partnerprofile_changelist'),
                },
                {
                    'label': 'Gross revenue',
                    'value': f'₹{revenue:,.0f}',
                    'hint': f'₹{today_revenue:,.0f} collected today · {today_bookings.count()} jobs today',
                    'tone': 'forest',
                    'url': reverse('admin:payments_payment_changelist'),
                },
                {
                    'label': 'Active coupons',
                    'value': Coupon.objects.filter(is_active=True).count(),
                    'hint': 'Create codes customers can apply at booking',
                    'tone': 'champagne',
                    'url': reverse('admin:coupons_coupon_changelist'),
                },
                {
                    'label': 'Live service cities',
                    'value': City.objects.filter(is_active=True).count(),
                    'hint': f'{City.objects.filter(is_active=False).count()} marked available soon',
                    'tone': 'sage',
                    'url': reverse('admin:locations_city_changelist'),
                },
            ],
            'catalog': {
                'categories': Category.objects.filter(is_active=True).count(),
                'services': Service.objects.filter(is_active=True).count(),
                'slides': HomeHeroSlide.objects.filter(is_active=True).count(),
                'coupons': Coupon.objects.filter(is_active=True).count(),
                'live_cities': City.objects.filter(is_active=True).count(),
                'soon_cities': City.objects.filter(is_active=False).count(),
            },
            'status_breakdown': status_breakdown,
            'assignment_breakdown': assignment_breakdown,
            'recent_bookings': recent,
            'recent_assignments': recent_assignments,
            'pending_partners': pending_partners,
        }
