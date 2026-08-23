from django.db import models
from django.utils.text import slugify

from apps.common.models import UUIDModel
from apps.locations.models import City


class Category(UUIDModel):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.TextField(blank=True)
    image_url = models.URLField(max_length=500, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name_plural = 'Categories'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Service(UUIDModel):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='services')
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=170, unique=True, blank=True)
    short_description = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    image_url = models.URLField(max_length=500, blank=True)
    duration_minutes = models.PositiveIntegerField(default=60)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        unique_together = ('category', 'name')

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f'{self.category.name}-{self.name}')
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ServicePackage(UUIDModel):
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name='packages')
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    description = models.TextField(blank=True)
    image_url = models.URLField(max_length=500, blank=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    discounted_price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_minutes = models.PositiveIntegerField(default=90)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['discounted_price', 'name']
        unique_together = ('service', 'name')

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f'{self.service.name}-{self.name}')
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class CityPackagePrice(UUIDModel):
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='package_prices')
    package = models.ForeignKey(ServicePackage, on_delete=models.CASCADE, related_name='city_prices')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discounted_price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('city', 'package')
        indexes = [models.Index(fields=['city', 'package'])]

    def __str__(self):
        return f'{self.city.name} - {self.package.name}'
