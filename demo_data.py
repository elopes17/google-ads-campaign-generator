"""Fixed fictional data for the public portfolio demonstration."""
from types import MappingProxyType

from werkzeug.datastructures import MultiDict


DEMO_FIELDS = MappingProxyType({
    'business_name': 'Fictional Home Services',
    'city': 'Boston',
    'state': 'Massachusetts',
    'service_area': 'Boston, Cambridge, and Somerville',
    'monthly_budget': '2500.00',
    'emergency_availability': 'Yes',
    'primary_goal': 'Phone calls and quote/service requests',
    'business_phone': '(202) 555-0147',
    'license_information': 'Fictional demo license: DEMO-001',
    'insurance_information': 'Fictional demo insurance statement',
    'additional_business_information': 'Sample information for portfolio demonstration only.',
    'website_url': 'https://example.com',
})

DEMO_SERVICES = ('Emergency Plumbing', 'Boiler Repair')


def demo_form_data():
    """Return a fresh form-shaped object so callers cannot mutate the fixture."""
    form = MultiDict(DEMO_FIELDS)
    form.setlist('services', list(DEMO_SERVICES))
    return form


def is_approved_demo_payload(data):
    """Identify only the exact, server-validated immutable demo fixture."""
    # Import locally so the fixture remains independent of validation module setup.
    from validation import validate_intake

    expected, errors = validate_intake(demo_form_data())
    if errors:
        raise RuntimeError('The fixed fictional demo data is invalid.')
    return data == expected
