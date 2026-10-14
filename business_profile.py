"""Normalize optional, user-provided business profile details."""
import re
import unicodedata


FIELD_LIMITS = {
    'business_phone': 30,
    'license_information': 160,
    'insurance_information': 160,
    'additional_business_information': 240,
}

FIELD_LABELS = {
    'business_phone': 'Business phone number',
    'license_information': 'License information',
    'insurance_information': 'Insurance information',
    'additional_business_information': 'Additional business information',
}

PHONE_PATTERNS = [
    re.compile(r'([0-9]{3})([0-9]{3})([0-9]{4})'),
    re.compile(r'([0-9]{3})-([0-9]{3})-([0-9]{4})'),
    re.compile(r'\(([0-9]{3})\) ([0-9]{3})-([0-9]{4})'),
    re.compile(r'([0-9]{3})\.([0-9]{3})\.([0-9]{4})'),
    re.compile(r'1-([0-9]{3})-([0-9]{3})-([0-9]{4})'),
    re.compile(r'\+1 ([0-9]{3}) ([0-9]{3}) ([0-9]{4})'),
]


def _has_unsupported_characters(value):
    """Reject controls and invisible formatting, while allowing normal whitespace."""
    return any(unicodedata.category(character).startswith('C') and not character.isspace()
               for character in value)


def normalize_optional_text(value, field, errors):
    """Collapse whitespace and validate one optional plain-text field."""
    value = value or ''
    label = FIELD_LABELS[field]
    if _has_unsupported_characters(value):
        errors.append(f'{label} contains unsupported control or formatting characters.')
    normalized = ' '.join(value.split())
    if len(normalized) > FIELD_LIMITS[field]:
        errors.append(f'{label} must be {FIELD_LIMITS[field]} characters or fewer.')
    return normalized


def normalize_phone(value, errors):
    """Return display and canonical forms for a syntactically valid +1 phone number."""
    raw = value or ''
    label = FIELD_LABELS['business_phone']
    if len(raw) > FIELD_LIMITS['business_phone']:
        errors.append(f'{label} must be {FIELD_LIMITS["business_phone"]} characters or fewer.')
    if _has_unsupported_characters(raw):
        errors.append(f'{label} contains unsupported control or formatting characters.')
    normalized = ' '.join(raw.split())
    if not normalized:
        return '', ''

    if not re.fullmatch(r'[0-9+().\-\s]+', normalized):
        errors.append(f'{label} contains unsupported characters.')
        return normalized, ''

    match = None
    for pattern in PHONE_PATTERNS:
        match = pattern.fullmatch(normalized)
        if match is not None:
            break
    if match is None:
        errors.append('Enter a valid 10-digit U.S. or Canadian phone number, optionally beginning with +1.')
        return normalized, ''

    area, exchange, subscriber = match.groups()
    display = f'({area}) {exchange}-{subscriber}'
    return display, f'+1{area}{exchange}{subscriber}'


def normalize_business_profile(form):
    """Return normalized optional profile data and any validation errors."""
    errors = []
    phone_display, phone_canonical = normalize_phone(form.get('business_phone', ''), errors)
    data = {
        'business_phone': phone_display,
        'business_phone_canonical': phone_canonical,
    }
    for field in ['license_information', 'insurance_information',
                  'additional_business_information']:
        data[field] = normalize_optional_text(form.get(field, ''), field, errors)
    return data, errors
