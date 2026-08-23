from django.contrib.admin.apps import AdminConfig


class BrolyticsAdminConfig(AdminConfig):
    default_site = 'apps.common.admin_site.BrolyticsAdminSite'
