from copy import deepcopy
from itertools import combinations, product
import json
import unittest

from landing_pages import generate_landing_pages
from landing_page_rules import LANDING_PAGE_RULES
from rules_library import RULES
from validation import SERVICES, validate_intake
from test_generator import submission


class LandingPageContentTests(unittest.TestCase):
    def data(self, services=None, **changes):
        data, errors = validate_intake(submission(SERVICES if services is None else services, **changes))
        self.assertEqual(errors, [])
        return data

    def test_all_63_combinations_preserve_mapping_and_order(self):
        for size in range(1, 7):
            for selected in combinations(SERVICES, size):
                with self.subTest(selected=selected):
                    # Reverse input and repeat a choice to check canonical ordering/deduplication.
                    data = self.data(list(reversed(selected)) + [selected[0]])
                    pages = generate_landing_pages(data)
                    self.assertEqual([p['service'] for p in pages], list(selected))
                    for page in pages:
                        rule = RULES[page['service']]
                        self.assertEqual(page['path'], rule['path'])
                        self.assertEqual(page['campaign'], rule['campaign'])

    def test_service_goal_availability_matrix(self):
        for service, goal, available in product(SERVICES,
                ['Phone calls', 'Quote/service requests', 'Phone calls and quote/service requests'], ['Yes', 'No']):
            with self.subTest(service=service, goal=goal, available=available):
                data = self.data([service], primary_goal=goal, emergency_availability=available, state='Massachusetts')
                before = deepcopy(data)
                pages = generate_landing_pages(data)
                self.assertEqual(pages, generate_landing_pages(data))
                self.assertEqual(data, before)
                page = pages[0]
                for field in ['hero_headline', 'hero_subheadline', 'description', 'service_area_heading',
                              'service_area_text', 'availability_text', 'final_cta', 'business_name']:
                    self.assertTrue(page[field], field)
                self.assertIn('Boston, Massachusetts', page['hero_subheadline'])
                self.assertIn(data['service_area'], page['service_area_text'])
                self.assertGreaterEqual(len(page['highlights']), 3)
                self.assertLessEqual(len(page['highlights']), 5)
                self.assertGreaterEqual(len(page['faqs']), 3)
                self.assertEqual(page['faqs'][0]['question'], LANDING_PAGE_RULES[service]['faqs'][0][0])
                expected = {'Phone calls': ['call'], 'Quote/service requests': ['form'],
                            'Phone calls and quote/service requests': ['call', 'form']}[goal]
                self.assertEqual([a['kind'] for a in page['cta']['actions']], expected)
                self.assertEqual(page['cta']['show_calls'], 'call' in expected)
                self.assertEqual(page['cta']['show_form'], 'form' in expected)
                self.assertEqual(page['preview_notice'], 'Local preview — not published.')
                text = json.dumps(page).lower()
                if available == 'No':
                    for claim in ['24/7', '24 hour', 'overnight', 'day or night', 'day-or-night',
                                  'round-the-clock', 'around the clock', 'any hour', 'always available']:
                        self.assertNotIn(claim, text)
                    self.assertEqual(page['availability_text'], 'Contact us to confirm availability.')
                else:
                    self.assertIn('24/7 emergency service', text)
                    self.assertIn('confirm availability for routine service', text)

    def test_service_specific_faqs_and_explicit_placeholders(self):
        pages = generate_landing_pages(self.data())
        self.assertEqual(len({p['description'] for p in pages}), 6)
        self.assertEqual(len({p['faqs'][0]['question'] for p in pages}), 6)
        for page in pages:
            for text in [item['text'] for item in page['business_information']] + [page['phone_placeholder']]:
                self.assertTrue(text.startswith('Placeholder:'))
            # Controlled inputs: curated copy must not invent business facts.
            copy = json.dumps(page).lower()
            for claim in ['licensed and insured', 'certified', 'years in business', 'five-star',
                          '5-star', 'free estimate', 'discount', 'guarantee', 'same-day',
                          'same day', 'immediate dispatch', 'arrival time', 'minutes', '$']:
                self.assertNotIn(claim, copy)
            self.assertNotIn('tel:', copy)
            for town in ['plymouth', 'kingston', 'duxbury']:
                self.assertNotIn(town, copy)

    def test_all_service_page_headings_use_title_case(self):
        expected_hero_headings = {
            'Emergency Plumbing': 'Help with Urgent Plumbing Problems',
            'Drain Cleaning': 'Discuss Your Drain Cleaning Needs',
            'Water Heater Repair/Replacement': 'Water Heater Repair and Replacement',
            'Heating Repair': 'Help with Heating System Problems',
            'Boiler Repair': 'Discuss Your Boiler Repair Needs',
            'Furnace Repair': 'Help with Furnace Heating Problems',
        }
        pages = generate_landing_pages(self.data())
        for page in pages:
            service = page['service']
            self.assertEqual(page['hero_headline'], expected_hero_headings[service])
            self.assertEqual(page['service_area_heading'], 'Service Area')
            self.assertEqual(page['final_cta']['heading'], f'Discuss Your {service} Needs')

    def test_long_inputs_and_output_independence(self):
        data = self.data(business_name='Very Long Business ' * 100,
                         city='Very Long City ' * 100, state='Massachusetts', service_area='Very Long Area ' * 100)
        pages = generate_landing_pages(data)
        for page in pages:
            self.assertEqual(page['business_name'], data['business_name'])
            self.assertIn(data['city'], page['hero_subheadline'])
            self.assertIn(data['service_area'], page['service_area_text'])
        pages[0]['highlights'].append('Changed output')
        pages[0]['business_information'].clear()
        pages[0]['faqs'][0]['answer'] = 'Changed output'
        fresh = generate_landing_pages(data)
        self.assertEqual(len(fresh[0]['highlights']), 4)
        self.assertTrue(fresh[0]['business_information'])
        self.assertNotEqual(fresh[0]['faqs'][0]['answer'], 'Changed output')


if __name__ == '__main__':
    unittest.main()
