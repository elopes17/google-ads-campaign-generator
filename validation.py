"""Validate browser submissions before generating a plan."""
from decimal import Decimal, InvalidOperation

from business_profile import normalize_business_profile
from website import normalize_website_url

SERVICES = [
    'Emergency Plumbing', 'Drain Cleaning', 'Water Heater Repair/Replacement',
    'Heating Repair', 'Boiler Repair', 'Furnace Repair',
]
GOALS = {
    'Phone calls': 'calls',
    'Quote/service requests': 'forms',
    'Phone calls and quote/service requests': 'both',
}


def validate_intake(form):
    data = {}
    errors = []
    for field in ['business_name', 'city', 'state', 'service_area']:
        data[field] = ' '.join(form.get(field, '').split())
        if not data[field]:
            errors.append(f"{field.replace('_', ' ').capitalize()} is required.")
    try:
        budget = Decimal(form.get('monthly_budget', '').strip())
        if not budget.is_finite() or budget < Decimal('0.01'):
            raise ValueError
        if budget != budget.quantize(Decimal('0.01')):
            raise ValueError
        data['monthly_budget'] = budget.quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError):
        errors.append('Monthly budget must be a positive USD amount with at most two decimal places.')
    availability = form.get('emergency_availability', '').strip()
    if availability not in ['Yes', 'No']:
        errors.append('Choose Yes or No for emergency availability.')
    data['emergency_availability'] = availability
    data['available_24_7'] = availability == 'Yes'
    goal = form.get('primary_goal', '').strip()
    if goal not in GOALS:
        errors.append('Choose a valid primary goal.')
    data['primary_goal'] = goal
    data['goal'] = GOALS.get(goal)
    selected = list(dict.fromkeys(form.getlist('services')))
    data['services'] = [service for service in selected if service in SERVICES]
    if not data['services']:
        errors.append('Please select at least one service.')
    if any(service not in SERVICES for service in selected):
        errors.append('An unknown service was submitted.')
    profile, profile_errors = normalize_business_profile(form)
    data.update(profile)
    errors.extend(profile_errors)
    data['website_url'], website_errors = normalize_website_url(form.get('website_url', ''))
    errors.extend(website_errors)
    return data, errors
