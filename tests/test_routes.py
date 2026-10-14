import unittest
from html.parser import HTMLParser
from app import app
from test_generator import submission


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_monthly_budget_input_and_value_retention(self):
        class BudgetParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.inputs = []

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == 'input' and attrs.get('name') == 'monthly_budget':
                    self.inputs.append(attrs)

        responses = [self.client.get('/')]
        for path in ['/generate', '/export']:
            response = self.client.post(path, data=submission([], monthly_budget='2500.01'))
            self.assertEqual(response.status_code, 400)
            responses.append(response)
        for index, response in enumerate(responses):
            with self.subTest(index=index):
                html = response.get_data(as_text=True)
                self.assertIn('<label for="monthly_budget">Monthly Google Ads Budget (USD)</label>', html)
                parser = BudgetParser()
                parser.feed(html)
                self.assertEqual(len(parser.inputs), 1)
                attrs = parser.inputs[0]
                self.assertEqual(attrs['type'], 'number')
                self.assertEqual(attrs['id'], 'monthly_budget')
                self.assertEqual(attrs['min'], '0.01')
                self.assertEqual(attrs['step'], '0.01')
                self.assertIn('required', attrs)
                self.assertEqual(attrs['value'], '' if index == 0 else '2500.01')

    def test_routes(self):
        self.assertEqual(self.client.get('/').status_code, 200)
        self.assertEqual(self.client.get('/generate').headers['Location'], '/')
        for path in ['/', '/generate']:
            response = self.client.post(path, data=submission(['Emergency Plumbing', 'Boiler Repair']))
            self.assertEqual(response.status_code, 200)
            html = response.get_data(as_text=True)
            self.assertIn('rules-based', html)
            self.assertNotIn('hardcoded', html)
            for slug in ['campaign-structure', 'keywords', 'negative-keywords', 'ads', 'budget-allocation', 'landing-pages', 'conversion-tracking', 'warnings']:
                self.assertIn(f'id="{slug}"', html)

    def test_errors_and_retention(self):
        response = self.client.post('/generate', data=submission([], city='Boston'))
        self.assertEqual(response.status_code, 400)
        self.assertIn('Please select at least one service.', response.get_data(as_text=True))
        self.assertIn('value="Boston"', response.get_data(as_text=True))
        self.assertEqual(self.client.post('/generate', data={}).status_code, 400)

    def test_full_state_in_summary(self):
        response = self.client.post('/generate', data=submission(city='Plymouth', state='Massachusetts'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('<dd>Plymouth, Massachusetts</dd>', response.get_data(as_text=True))

    def test_new_service_and_escaping(self):
        response = self.client.post('/generate', data=submission(['Drain Cleaning'], business_name='<script>bad</script>'))
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertNotIn('not implemented', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>', html)
        self.assertIn('Headlines (15)', html)
        self.assertIn('Descriptions (4)', html)
