"""Deterministic generation from validated inputs and local templates."""
from decimal import Decimal, ROUND_HALF_UP
from locations import short_state
from rules_library import RULES, CTA, HEADLINES, DESCRIPTIONS, NEGATIVES, CONVERSIONS


def section(slug, title, headers, rows):
    return {'id': slug, 'title': title, 'headers': headers, 'rows': rows}


def make_assets(templates, context, limit, warnings, service):
    assets = []
    for full, short in templates:
        text = full.format(**context)
        notes = 'Template'
        if len(text) > limit:
            text = short.format(**context)
            notes = 'Predefined shorter alternative'
            warning = f'{service}: shorter ad alternatives were used because some submitted text exceeds asset limits.'
            if warning not in warnings:
                warnings.append(warning)
        # All fallback templates are bounded; never truncate submitted names.
        if len(text) > limit:
            raise ValueError('A predefined ad alternative exceeds its character limit.')
        assets.append({'text': text, 'count': len(text), 'notes': notes})
    return assets


def generate_campaign(data):
    supported = [service for service in RULES if service in data['services']]
    warnings = []
    campaigns = list(dict.fromkeys(RULES[service]['campaign'] for service in supported))
    structure, keywords, negatives, ads, pages = [], [], [], [], []
    cta = CTA[data['goal']]
    state_abbreviation = short_state(data['state'])
    for service in supported:
        rule = RULES[service]
        campaign = rule['campaign']
        structure.append([campaign, service])
        for keyword in rule['keywords']:
            if keyword['requires_24_7'] and not data['available_24_7']:
                continue
            text = keyword['text'].format(city=data['city'], state=state_abbreviation)
            keywords.append([campaign, service, text, keyword['match'], keyword['notes']])
        negatives.extend([list(row) for row in NEGATIVES[service]])
        availability = rule['availability_yes'] if data['available_24_7'] else rule['availability_no']
        context = {**data, **rule,
                   'state': state_abbreviation,
                   'availability_headline': availability[0], 'availability_second': availability[1],
                   'availability_description': availability[2], 'availability_short': availability[3],
                   'cta_headline': cta['headline'], 'cta_text': cta['text'],
                   'cta_short': {'calls': 'Call Our Team', 'forms': 'Send a Service Request', 'both': 'Call or Send a Request'}[data['goal']]}
        ads.append({'group': service, 'campaign': campaign,
                    'headlines': make_assets(rule.get('headline_pairs', HEADLINES), context, 30, warnings, service),
                    'descriptions': make_assets(rule.get('description_pairs', DESCRIPTIONS), context, 90, warnings, service)})
        page_message = f"{data['business_name']}: {rule['service_short']} in {data['city']}, {data['state']}. Serving {data['service_area']}."
        if 'landing_message' in rule:
            page_message += ' ' + rule['landing_message'] + '.'
        if data['available_24_7']:
            page_message += ' Available 24/7.'
        pages.append([campaign, service, rule['path'], page_message, cta['landing']])

    budget_rows = []
    if campaigns:
        cents = int(data['monthly_budget'] * 100)
        base, remainder = divmod(cents, len(campaigns))
        for index, campaign in enumerate(campaigns):
            monthly = Decimal(base + (1 if index < remainder else 0)) / 100
            daily = (monthly / Decimal('30.4')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            budget_rows.append([campaign, f'${monthly:,.2f}', f'${daily:,.2f}',
                                '100%' if len(campaigns) == 1 else '50%', 'Allocation across created campaigns'])
        budget_rows.append(['Total', f"${data['monthly_budget']:,.2f}",
                            f"${sum(Decimal(row[2].replace('$', '').replace(',', '')) for row in budget_rows):,.2f}", '100%', 'Entered monthly budget'])
        if remainder:
            warnings.append('The equal budget split leaves one extra cent; Plumbing Services receives that cent.')
    else:
        warnings.append('No implemented services were selected. No campaigns or budget allocations were created.')

    conversions = []
    if campaigns:
        for original in CONVERSIONS:
            row = list(original)
            is_call = row[1] == 'Call'
            is_form = row[1] == 'Form Submission'
            primary = (is_call and data['goal'] in ['calls', 'both']) or (is_form and data['goal'] in ['forms', 'both'])
            row[2] = 'Primary' if primary else 'Secondary'
            conversions.append(row)
    warnings.append('Landing-page previews are local only and are not published. Conversion tracking remains a recommendation and has not been configured.')
    result = {'sections': [
        section('campaign-structure', 'Campaign structure', ['Campaign', 'Ad Group'], structure),
        section('keywords', 'Keywords', ['Campaign', 'Ad Group', 'Keyword', 'Match Type', 'Intent/Notes'], keywords),
        section('negative-keywords', 'Negative keywords', ['Campaign', 'Ad Group', 'Negative Keyword', 'Match Type', 'Reason'], negatives),
        section('budget-allocation', 'Budget allocation', ['Campaign', 'Monthly Budget', 'Avg. Daily Budget', 'Share of Total', 'Rationale'], budget_rows),
        section('landing-pages', 'Landing pages', ['Campaign', 'Ad Group', 'Recommended Landing Page', 'Primary Message', 'Primary CTA'], pages),
        section('conversion-tracking', 'Conversion tracking', ['Conversion Action', 'Type', 'Primary/Secondary', 'What It Measures', 'Why It Matters'], conversions),
    ], 'ads': ads, 'warnings': warnings}
    result['sections'][3]['note'] = 'Daily budgets use monthly allocation divided by 30.4, rounded to cents. Equal allocation is a starting recommendation.'
    return result
