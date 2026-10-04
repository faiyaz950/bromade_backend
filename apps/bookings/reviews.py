from django.db.models import Avg, Count

from .models import BookingRating


def _display_name(user):
    profile = getattr(user, 'customer_profile', None)
    name = (getattr(profile, 'full_name', '') or f'{user.first_name} {user.last_name}').strip()
    if not name:
        return 'Verified customer'
    parts = name.split()
    if len(parts) == 1:
        return parts[0]
    return f'{parts[0]} {parts[-1][0]}.'


def _photo_url(request, field):
    if not field:
        return None
    url = field.url
    return request.build_absolute_uri(url) if request is not None else url


def rating_summary(ratings, *, request=None, limit=20, with_photos=False):
    """Average, star distribution and the most recent reviews for a BookingRating queryset."""
    stats = ratings.aggregate(average=Avg('stars'), count=Count('id'))
    counts = dict(ratings.values_list('stars').annotate(n=Count('id')).values_list('stars', 'n'))
    recent = (
        ratings.select_related('booking__customer__customer_profile')
        .prefetch_related('booking__items')
        .order_by('-created_at')[:limit]
    )
    reviews = []
    for rating in recent:
        booking = rating.booking
        item = next(iter(booking.items.all()), None)
        reviews.append(
            {
                'id': str(rating.id),
                'stars': rating.stars,
                'comment': rating.comment,
                'customer_name': _display_name(booking.customer),
                'service_name': item.package_name if item else '',
                'created_at': rating.created_at.isoformat(),
                'photo_url': _photo_url(request, booking.completion_photo) if with_photos else None,
            }
        )
    return {
        'average': round(float(stats['average'] or 0), 1),
        'count': stats['count'],
        'distribution': {str(star): counts.get(star, 0) for star in range(5, 0, -1)},
        'reviews': reviews,
    }


def ratings_for_partner(partner):
    from .models import BookingAssignment

    ids = BookingRating.objects.filter(
        booking__assignments__partner=partner,
        booking__assignments__status=BookingAssignment.Status.ACCEPTED,
    ).values('id')
    return BookingRating.objects.filter(id__in=ids)


def ratings_for_service(service_id):
    ids = BookingRating.objects.filter(booking__items__package__service_id=service_id).values('id')
    return BookingRating.objects.filter(id__in=ids)
