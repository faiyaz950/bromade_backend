from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render

from .models import AppRelease


def health(request):
    return JsonResponse({'status': 'ok'})


def app_release(request):
    """Public: versions the app compares itself against to prompt updates."""
    release = AppRelease.objects.filter(
        app=request.GET.get('app', AppRelease.App.CUSTOMER),
        platform=request.GET.get('platform', ''),
    ).first()
    if release is None:
        return JsonResponse({'latest_version': None, 'min_supported_version': None, 'store_url': '', 'message': ''})
    return JsonResponse(
        {
            'latest_version': release.latest_version,
            'min_supported_version': release.min_supported_version or None,
            'store_url': release.store_url,
            'message': release.message,
        }
    )


def _legal_page(template, title):
    def view(request):
        return render(
            request,
            template,
            {
                'title': title,
                'brand': 'Demess',
                'company': settings.COMPANY_NAME,
                'support_email': settings.SUPPORT_EMAIL,
                'effective_date': settings.LEGAL_EFFECTIVE_DATE,
            },
        )

    return view


privacy_policy = _legal_page('legal/privacy.html', 'Privacy Policy')
terms = _legal_page('legal/terms.html', 'Terms & Conditions')
delete_account = _legal_page('legal/delete_account.html', 'Delete your account')
