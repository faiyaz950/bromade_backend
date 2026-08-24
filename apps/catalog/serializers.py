from rest_framework import serializers

from .models import Category, HomeHeroSlide, Service, ServicePackage, ServiceProcessStep


def absolute_media_url(request, value: str) -> str:
    if not value:
        return ''
    if value.startswith('http://') or value.startswith('https://'):
        return value
    if request is None:
        return value
    return request.build_absolute_uri(value)


class HomeHeroSlideSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = HomeHeroSlide
        fields = ('id', 'title', 'subtitle', 'image_url', 'sort_order')

    def get_image_url(self, obj):
        return absolute_media_url(self.context.get('request'), obj.resolved_image_url())


class ServicePackageSerializer(serializers.ModelSerializer):
    effective_price = serializers.SerializerMethodField()
    effective_discounted_price = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ServicePackage
        fields = (
            'id',
            'name',
            'slug',
            'description',
            'image_url',
            'base_price',
            'discounted_price',
            'duration_minutes',
            'effective_price',
            'effective_discounted_price',
        )

    def _city_price(self, obj):
        city_id = self.context.get('city_id')
        if not city_id:
            return None
        return obj.city_prices.filter(city_id=city_id, is_active=True).first()

    def get_effective_price(self, obj):
        city_price = self._city_price(obj)
        return city_price.price if city_price else obj.base_price

    def get_effective_discounted_price(self, obj):
        city_price = self._city_price(obj)
        return city_price.discounted_price if city_price else obj.discounted_price

    def get_image_url(self, obj):
        raw = obj.image_url or obj.service.image_url or obj.service.category.image_url
        return absolute_media_url(self.context.get('request'), raw)


class ServiceProcessStepSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ServiceProcessStep
        fields = ('id', 'title', 'description', 'image_url', 'sort_order')

    def get_image_url(self, obj):
        return absolute_media_url(self.context.get('request'), obj.resolved_image_url())


class ServiceSerializer(serializers.ModelSerializer):
    packages = ServicePackageSerializer(many=True, read_only=True)
    image_url = serializers.SerializerMethodField()
    included_items = serializers.SerializerMethodField()
    excluded_items = serializers.SerializerMethodField()
    process_steps = ServiceProcessStepSerializer(many=True, read_only=True)

    class Meta:
        model = Service
        fields = (
            'id',
            'name',
            'slug',
            'headline',
            'short_description',
            'description',
            'image_url',
            'duration_minutes',
            'included_items',
            'excluded_items',
            'process_steps',
            'packages',
        )

    def _inclusion_texts(self, obj, kind):
        cached = getattr(obj, '_prefetched_objects_cache', {}).get('inclusions')
        items = cached if cached is not None else obj.inclusions.all()
        return [item.text for item in items if item.kind == kind]

    def get_included_items(self, obj):
        return self._inclusion_texts(obj, 'included')

    def get_excluded_items(self, obj):
        return self._inclusion_texts(obj, 'excluded')

    def get_image_url(self, obj):
        return absolute_media_url(self.context.get('request'), obj.image_url or obj.category.image_url)


class CategorySerializer(serializers.ModelSerializer):
    services = ServiceSerializer(many=True, read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ('id', 'name', 'slug', 'description', 'image_url', 'services')

    def get_image_url(self, obj):
        return absolute_media_url(self.context.get('request'), obj.image_url)


class PackageDetailSerializer(ServicePackageSerializer):
    service = serializers.SerializerMethodField()

    class Meta(ServicePackageSerializer.Meta):
        fields = ServicePackageSerializer.Meta.fields + ('service',)

    def get_service(self, obj):
        request = self.context.get('request')
        return {
            'id': str(obj.service_id),
            'name': obj.service.name,
            'category': obj.service.category.name,
            'image_url': absolute_media_url(request, obj.service.image_url or obj.service.category.image_url),
        }
