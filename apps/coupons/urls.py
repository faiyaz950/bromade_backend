from django.urls import path

from .views import CouponListView, CouponValidateView

urlpatterns = [
    path('', CouponListView.as_view(), name='coupon-list'),
    path('validate/', CouponValidateView.as_view(), name='coupon-validate'),
]
