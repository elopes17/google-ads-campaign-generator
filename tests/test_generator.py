import json
import unittest
from decimal import Decimal
from itertools import product, combinations
from werkzeug.datastructures import MultiDict
from generator import generate_campaign
from validation import validate_intake, SERVICES
from rules_library import NEGATIVES, RULES
from locations import short_state


def submission(services=None, **changes):
    values = {'business_name': 'Acme Home Services', 'city': 'Boston', 'state': 'MA',
              'service_area': 'Boston, Cambridge, Somerville', 'monthly_budget': '2500.01',
              'emergency_availability': 'Yes', 'primary_goal': 'Phone calls'}
    values.update(changes)
    form = MultiDict(values)
    form.setlist('services', services if services is not None else ['Emergency Plumbing'])
    return form


class GeneratorTests(unittest.TestCase):
    def test_state_abbreviations(self):
        for state in ['Massachusetts', 'massachusetts', 'MA']:
            with self.subTest(state=state):
                data, errors = validate_intake(submission(['Emergency Plumbing', 'Boiler Repair'],
                    city='Plymouth', state=state))
                self.assertFalse(errors)
                self.assertEqual(data['state'], state)
                plan = generate_campaign(data)
                self.assertIn('emergency plumber Plymouth MA', [r[2] for r in plan['sections'][1]['rows']])
                self.assertIn('boiler repair Plymouth MA', [r[2] for r in plan['sections'][1]['rows']])
                for ad in plan['ads']:
                    text = ' '.join(a['text'] for a in ad['headlines'] + ad['descriptions'])
                    self.assertNotIn('Massachusetts', text)
                    self.assertIn('Plymouth, MA', text)
                for row in plan['sections'][4]['rows']:
                    self.assertIn(f'Plymouth, {state}.', row[3])
        self.assertEqual(short_state('Unknown State'), 'Unknown State')

    def test_curated_keyword_lists(self):
        for service, yes_count, no_count in [('Emergency Plumbing', 21, 14), ('Boiler Repair', 22, 20)]:
            for availability, expected_count in [('Yes', yes_count), ('No', no_count)]:
                with self.subTest(service=service, availability=availability):
                    data, errors = validate_intake(submission([service], emergency_availability=availability))
                    self.assertFalse(errors)
                    rows = generate_campaign(data)['sections'][1]['rows']
                    pairs = {(row[2], row[3]) for row in rows}
                    self.assertEqual(len(rows), expected_count)
                    self.assertEqual(len(pairs), expected_count)
                    near_me = [row for row in rows if 'near me' in row[2]]
                    self.assertEqual(len(near_me), 2)
                    location_rows = [row for row in rows if 'Boston MA' in row[2]]
                    expected_locations = 3 if service == 'Boiler Repair' else (4 if availability == 'Yes' else 2)
                    self.assertEqual(len(location_rows), expected_locations)
                    phrase_only = 'leaking pipe plumber' if service == 'Emergency Plumbing' else 'boiler service'
                    self.assertIn((phrase_only, 'Phrase'), pairs)
                    self.assertNotIn((phrase_only, 'Exact'), pairs)
                    self.assertNotIn((phrase_only + ' near me', 'Phrase'), pairs)
                    self.assertNotIn((phrase_only + ' Boston MA', 'Phrase'), pairs)

    def test_service_availability_goal_matrix(self):
        choices = [list(group) for size in range(1, 7) for group in combinations(SERVICES, size)]
        for services, available, goal in product(choices, ['Yes', 'No'],
                ['Phone calls', 'Quote/service requests', 'Phone calls and quote/service requests']):
            with self.subTest(services=services, available=available, goal=goal):
                data, errors = validate_intake(submission(services, emergency_availability=available, primary_goal=goal))
                self.assertEqual(errors, [])
                plan = generate_campaign(data)
                self.assertEqual([a['group'] for a in plan['ads']], services)
                expected = {('Plumbing Services' if s in SERVICES[:3] else 'Heating Services') for s in services}
                self.assertEqual({r[0] for r in plan['sections'][0]['rows']}, expected)
                rows = plan['sections'][3]['rows'][:-1]
                amounts = [Decimal(r[1].replace('$', '').replace(',', '')) for r in rows]
                self.assertEqual(sum(amounts), data['monthly_budget'])
                if len(rows) == 1:
                    self.assertEqual(rows[0][3], '100%')
                else:
                    self.assertEqual(amounts, [Decimal('1250.01'), Decimal('1250.00')])
                for ad in plan['ads']:
                    self.assertEqual(len(ad['headlines']), 15)
                    self.assertEqual(len({asset['text'] for asset in ad['headlines']}), 15)
                    self.assertEqual(len(ad['descriptions']), 4)
                    self.assertEqual(len({asset['text'] for asset in ad['descriptions']}), 4)
                    for key, limit in [('headlines', 30), ('descriptions', 90)]:
                        for asset in ad[key]:
                            self.assertEqual(asset['count'], len(asset['text']))
                            self.assertLessEqual(asset['count'], limit)
                            self.assertNotIn(data['service_area'], asset['text'])
                    texts = ' '.join(a['text'] for a in ad['headlines'] + ad['descriptions'])
                    self.assertIn('Boston', texts)
                    self.assertIn('Acme Home Services', texts)
                    if goal == 'Phone calls':
                        self.assertNotIn('online', texts)
                    elif goal == 'Quote/service requests':
                        self.assertNotIn('Call', texts)
                    else:
                        self.assertIn('Call or request service online.', texts)
                keywords = json.dumps(plan['sections'][1]['rows'])
                self.assertIn('Boston MA', keywords)
                self.assertNotIn('Plymouth', json.dumps(plan))
                if available == 'No':
                    output = json.dumps(plan).lower()
                    for claim in ['24/7', '24 hour', 'day or night', 'any hour', '24 hours', 'round-the-clock']:
                        self.assertNotIn(claim, output)
                else:
                    self.assertIn('24/7', json.dumps(plan))
                for row in plan['sections'][4]['rows']:
                    self.assertIn(data['service_area'], row[3])
                primary = [r[1] for r in plan['sections'][5]['rows'] if r[2] == 'Primary']
                expected_types = {'Phone calls': {'Call'}, 'Quote/service requests': {'Form Submission'},
                                  'Phone calls and quote/service requests': {'Call', 'Form Submission'}}
                self.assertEqual(set(primary), expected_types[goal])

    def test_long_input_fallbacks(self):
        for availability, goal in product(['Yes', 'No'],
                ['Phone calls', 'Quote/service requests', 'Phone calls and quote/service requests']):
            with self.subTest(availability=availability, goal=goal):
                data, errors = validate_intake(submission(SERVICES,
                    business_name='Very Long Business Name ' * 20, city='Very Long City ' * 20,
                    state='Long State ' * 20, emergency_availability=availability, primary_goal=goal))
                self.assertFalse(errors)
                plan = generate_campaign(data)
                self.assertTrue(any('shorter' in w for w in plan['warnings']))
                for ad in plan['ads']:
                    self.assertEqual(len(ad['headlines']), 15)
                    self.assertEqual(len({asset['text'] for asset in ad['headlines']}), 15)
                    self.assertEqual(len(ad['descriptions']), 4)
                    self.assertEqual(len({asset['text'] for asset in ad['descriptions']}), 4)
                    for key, limit in [('headlines', 30), ('descriptions', 90)]:
                        self.assertTrue(all(a['count'] <= limit for a in ad[key]))
                self.assertIn(data['business_name'], plan['sections'][4]['rows'][0][3])

    def test_curated_negatives_and_landing_paths(self):
        for service in SERVICES:
            data, errors = validate_intake(submission([service], state='Massachusetts'))
            self.assertFalse(errors)
            plan = generate_campaign(data)
            self.assertEqual(plan['sections'][2]['rows'], NEGATIVES[service])
            page = plan['sections'][4]['rows'][0]
            self.assertEqual(page[0], RULES[service]['campaign'])
            self.assertEqual(page[2], RULES[service]['path'])
            self.assertIn('Boston, Massachusetts.', page[3])
            self.assertFalse(any('not implemented' in w for w in plan['warnings']))

    def test_all_service_keyword_counts(self):
        counts = {'Emergency Plumbing': (21, 14), 'Drain Cleaning': (22, 22),
                  'Water Heater Repair/Replacement': (24, 24), 'Heating Repair': (24, 22),
                  'Boiler Repair': (22, 20), 'Furnace Repair': (22, 20)}
        for service, expected_counts in counts.items():
            for availability, count in zip(['Yes', 'No'], expected_counts):
                with self.subTest(service=service, availability=availability):
                    data, errors = validate_intake(submission([service], emergency_availability=availability))
                    self.assertFalse(errors)
                    rows = generate_campaign(data)['sections'][1]['rows']
                    self.assertEqual(len(rows), count)
                    self.assertEqual(len({(r[2], r[3]) for r in rows}), count)
                    original = [
                        (keyword['text'].format(city='Boston', state='MA'), keyword['match'])
                        for keyword in RULES[service]['keywords']
                        if availability == 'Yes' or not keyword['requires_24_7']
                    ]
                    self.assertEqual([(r[2], r[3]) for r in rows],
                                     original)
                    for town in ['plymouth', 'kingston', 'duxbury']:
                        self.assertNotIn(town, json.dumps(generate_campaign(data)).lower())

    def test_validation(self):
        for field in ['business_name', 'city', 'state', 'service_area', 'primary_goal', 'emergency_availability', 'monthly_budget']:
            with self.subTest(field=field):
                self.assertTrue(validate_intake(submission(**{field: '   '}))[1])
        for budget in ['0', '-1', 'NaN', 'Infinity', 'abc', '1.001', '1e9999']:
            self.assertTrue(validate_intake(submission(monthly_budget=budget))[1])
        self.assertTrue(validate_intake(submission([]))[1])
        self.assertTrue(validate_intake(submission(['Unknown']))[1])
        self.assertTrue(validate_intake(submission(primary_goal='unknown'))[1])
        self.assertTrue(validate_intake(submission(emergency_availability='Maybe'))[1])
        data, errors = validate_intake(submission(['Boiler Repair', 'Boiler Repair'], city='  New   York  '))
        self.assertFalse(errors)
        self.assertEqual(data['city'], 'New York')
        self.assertEqual(data['services'], ['Boiler Repair'])

    def test_tiny_and_even_budgets(self):
        for amount in ['0.01', '0.02', '2500.00']:
            data, errors = validate_intake(submission(['Emergency Plumbing', 'Boiler Repair'], monthly_budget=amount))
            self.assertFalse(errors)
            rows = generate_campaign(data)['sections'][3]['rows'][:-1]
            self.assertEqual(sum(Decimal(r[1].replace('$', '').replace(',', '')) for r in rows), Decimal(amount))
