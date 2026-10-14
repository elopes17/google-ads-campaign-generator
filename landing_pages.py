"""Stateless landing-page content, separate from campaign and Excel data."""
from demo_data import is_approved_demo_payload
from landing_page_rules import LANDING_PAGE_RULES, PHONE_PLACEHOLDER, TRUST_PLACEHOLDERS
from rules_library import RULES


_LOWERCASE_TITLE_WORDS = frozenset({
    'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'from', 'in', 'of', 'on', 'or', 'the', 'to', 'with',
})


def _title_case_heading(text):
    """Title-case curated headings while retaining conventional short words."""
    words = text.split()
    def capitalize_word(word):
        return '/'.join(part[:1].upper() + part[1:] for part in word.split('/'))

    return ' '.join(
        word.lower() if index and word.lower() in _LOWERCASE_TITLE_WORDS else capitalize_word(word)
        for index, word in enumerate(words)
    )


def generate_landing_pages(data, demo_mode=None):
    if demo_mode is None:
        demo_mode = is_approved_demo_payload(data)
    pages = []
    for service, rule in RULES.items():
        if service not in data['services']:
            continue
        copy = LANDING_PAGE_RULES[service]
        show_calls = data['goal'] in ['calls', 'both']
        show_form = data['goal'] in ['forms', 'both']
        actions = []
        phone_provided = bool(data.get('business_phone_canonical'))
        phone = {
            'provided': phone_provided,
            'display': data.get('business_phone', ''),
            'tel_href': f"tel:{data['business_phone_canonical']}" if phone_provided else None,
        }
        if show_calls:
            actions.append({
                'kind': 'call',
                'label': f"Call {phone['display']}" if phone_provided else 'Call about service',
                'href': phone['tel_href'] if phone_provided else '#phone-placeholder',
            })
        if show_form:
            actions.append({'kind': 'form', 'label': 'Request service', 'href': '#request-service'})
        availability = ('24/7 emergency service is available. Contact us to confirm availability for routine service.'
                        if data['available_24_7'] else 'Contact us to confirm availability.')
        pages.append({
            'service': service,
            'campaign': rule['campaign'],
            'path': rule['path'],
            'business_name': data['business_name'],
            'demo_mode': demo_mode,
            'preview_notice': 'Local preview — not published.',
            'demo_notice': 'Fictional demonstration — sample information only.' if demo_mode else '',
            'hero_headline': _title_case_heading(copy['headline']),
            'hero_subheadline': f"{service} from {data['business_name']} in {data['city']}, {data['state']}.",
            'cta': {'show_calls': show_calls, 'show_form': show_form, 'actions': actions},
            'description': copy['description'].format(business_name=data['business_name']),
            'highlights': list(copy['highlights']),
            'service_area_heading': 'Service Area',
            'service_area_text': f"Serving {data['service_area']}. Contact us to confirm service at your address.",
            'availability_text': availability,
            'phone': phone,
            'business_information_heading': (
                'Fictional Demo Information' if demo_mode else 'Provided Business Information'
            ),
            'business_information_disclosure': (
                'These details are fictional and are included only to demonstrate the application.'
                if demo_mode else
                'Supplied details were provided by the user and were not independently verified by the application.'
            ),
            'business_information': [
                {'key': 'license', 'label': 'License Information',
                 'text': data.get('license_information', '') or TRUST_PLACEHOLDERS[0],
                 'provided': bool(data.get('license_information', ''))},
                {'key': 'insurance', 'label': 'Insurance Information',
                 'text': data.get('insurance_information', '') or TRUST_PLACEHOLDERS[1],
                 'provided': bool(data.get('insurance_information', ''))},
                {'key': 'additional', 'label': 'Additional Business Information',
                 'text': data.get('additional_business_information', '') or TRUST_PLACEHOLDERS[2],
                 'provided': bool(data.get('additional_business_information', ''))},
            ],
            'phone_disclosure': (
                'This is a fictional example phone number used for demonstration only.'
                if demo_mode else
                'This phone number was provided by the user and was not independently verified by the application.'
            ),
            'phone_placeholder': PHONE_PLACEHOLDER,
            'faqs': [{'question': question, 'answer': answer} for question, answer in copy['faqs']] + [
                {'question': 'How can I confirm service availability?', 'answer': availability},
            ],
            'final_cta': {'heading': _title_case_heading(f'Discuss your {service.lower()} needs'),
                          'text': 'Use the contact option below to discuss your service needs.'
                                  if len(actions) == 1 else 'Choose a contact option to discuss your service needs.'},
        })
    return pages
