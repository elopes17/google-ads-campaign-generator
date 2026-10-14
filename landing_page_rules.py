"""Curated page copy only; campaign names and paths stay in RULES."""

LANDING_PAGE_RULES = {
    'Emergency Plumbing': {
        'headline': 'Help with urgent plumbing problems',
        'description': 'Discuss burst pipes, leaking pipes, and other urgent plumbing needs with {business_name}. Describe the problem so the next steps can be discussed.',
        'highlights': ['Burst pipe repair needs', 'Leaking pipe concerns', 'Urgent plumbing service inquiries', 'Questions about plumbing repairs'],
        'faqs': [
            ('What problems can I ask about?', 'You can ask about burst pipes, leaking pipes, and urgent plumbing repair needs.'),
            ('What details should I share?', 'Describe where the leak or pipe problem is and what you have noticed. Contact the business to discuss next steps.'),
        ],
    },
    'Drain Cleaning': {
        'headline': 'Discuss your drain cleaning needs',
        'description': '{business_name} provides drain cleaning service. Describe slow drains, clogs, or sewer backups to discuss the service you need.',
        'highlights': ['Slow or clogged drains', 'Drain cleaning inquiries', 'Sewer line cleaning needs', 'Sewer backup concerns'],
        'faqs': [
            ('Can I ask about a slow drain?', 'Yes. Describe which drain is affected and whether the problem is recurring.'),
            ('What if I have a sewer backup?', 'Explain the backup and where it is occurring so the business can discuss the appropriate service.'),
        ],
    },
    'Water Heater Repair/Replacement': {
        'headline': 'Water heater repair and replacement',
        'description': 'Discuss water heater repair, replacement, or installation with {business_name}. Share concerns about leaks, failing hot water, or a water heater that is not working.',
        'highlights': ['Water heater repair needs', 'Replacement and installation inquiries', 'No hot water concerns', 'Leaking water heater concerns'],
        'faqs': [
            ('Should I ask about repair or replacement?', 'Describe the problem and ask the business to discuss repair and replacement options. This preview does not determine which option is suitable.'),
            ('Can I ask about a new installation?', 'Yes. Share your installation needs with the business to discuss the next steps.'),
        ],
    },
    'Heating Repair': {
        'headline': 'Help with heating system problems',
        'description': '{business_name} provides heating repair service. Discuss a home without heat or a heating system that is not working as expected.',
        'highlights': ['Heating system repair needs', 'No heat concerns', 'Heating service inquiries', 'Questions about heating problems'],
        'faqs': [
            ('What if my home has no heat?', 'Describe the loss of heat and any changes you have noticed so the business can discuss your repair needs.'),
            ('What should I share about my heating system?', 'Explain the symptoms and when they started. The business can discuss which details are needed next.'),
        ],
    },
    'Boiler Repair': {
        'headline': 'Discuss your boiler repair needs',
        'description': 'Discuss boiler repair and service with {business_name}. Share concerns about a boiler leak or a boiler that is not providing heat.',
        'highlights': ['Boiler repair inquiries', 'Boiler leaks', 'No heat from the boiler', 'Boiler service questions'],
        'faqs': [
            ('Can I ask about a leaking boiler?', 'Yes. Describe the leak and where it appears so the business can discuss your boiler repair needs.'),
            ('What if my boiler is not heating?', 'Share what you have noticed and when the heating problem began. Contact the business to discuss next steps.'),
        ],
    },
    'Furnace Repair': {
        'headline': 'Help with furnace heating problems',
        'description': '{business_name} provides furnace repair service. Discuss a furnace that is not heating, is blowing cold air, or is experiencing other heating problems.',
        'highlights': ['Furnace repair inquiries', 'Furnace not heating', 'Cold air from the furnace', 'No heat concerns'],
        'faqs': [
            ('Can I ask about a furnace blowing cold air?', 'Yes. Explain what you have noticed and when the problem began so the business can discuss repair needs.'),
            ('What information is useful for a furnace inquiry?', 'Describe the heating problem and any recent changes. The business can discuss what information is needed next.'),
        ],
    },
}

TRUST_PLACEHOLDERS = [
    'Placeholder: add verified license information, if applicable.',
    'Placeholder: add verified insurance information, if applicable.',
    'Placeholder: add verified additional business information, if applicable.',
]
PHONE_PLACEHOLDER = 'Placeholder: add the verified business phone number.'
