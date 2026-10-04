from django.urls import path

from .views import CouponListView, CouponValidateView, ReferralApplyView, ReferralView

urlpatterns = [
    path('', CouponListView.as_view(), name='coupon-list'),
    path('validate/', CouponValidateView.as_view(), name='coupon-validate'),
    path('referral/', ReferralView.as_view(), name='referral'),
    path('referral/apply/', ReferralApplyView.as_view(), name='referral-apply'),
]
