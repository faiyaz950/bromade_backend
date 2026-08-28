# Booking MVP API

## Auth
- `POST /api/v1/auth/otp/request/`
- `POST /api/v1/auth/otp/verify/`
- `GET /api/v1/auth/me/`

## Locations
- `GET /api/v1/cities/`
- `POST /api/v1/coverage/` body: `{ latitude, longitude, city_name, place_names, city_id }`
- `GET /api/v1/addresses/`
- `POST /api/v1/addresses/`
- `GET /api/v1/addresses/{id}/`
- `PATCH /api/v1/addresses/{id}/`
- `DELETE /api/v1/addresses/{id}/`
- `POST /api/v1/addresses/{id}/set-default/`

## Catalog
- `GET /api/v1/catalog/categories/?city_id={uuid}`
- `GET /api/v1/catalog/packages/{id}/?city_id={uuid}`

## Bookings
- `GET /api/v1/bookings/price-summary/?package_id={uuid}&city_id={uuid}`
- `POST /api/v1/bookings/create/`
- `GET /api/v1/bookings/`
- `GET /api/v1/bookings/{id}/`
- `POST /api/v1/bookings/{id}/confirm/`

## Payments
- `POST /api/v1/payments/orders/`
- `POST /api/v1/payments/verify/`
- `POST /api/v1/payments/webhooks/razorpay/`
