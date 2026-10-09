def normalize_phone_number(value):
    if value is None:
        return None
    raw = str(value).strip().replace(' ', '').replace('-', '')
    if not raw:
        return None
    if raw.startswith('+'):
        return raw
    if raw.startswith('91') and len(raw) == 12:
        return f'+{raw}'
    if raw.isdigit() and len(raw) == 10:
        return f'+91{raw}'
    return f'+{raw}'
