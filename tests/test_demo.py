import unittest
from html.parser import HTMLParser
from io import BytesIO
from zipfile import ZipFile

from app import app, summarize_plan
from demo_data import DEMO_FIELDS, DEMO_SERVICES, demo_form_data, is_approved_demo_payload
from generator import generate_campaign
from landing_page_export import INDEX_PATH, README_PATH, service_filename
from validation import validate_intake


class FormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form':
            self.current = {'attrs': attrs, 'inputs': []}
            self.forms.append(self.current)
        elif tag == 'input' and self.current is not None:
            self.current['inputs'].append(attrs)

    def handle_endtag(self, tag):
        if tag == 'form':
            self.current = None


class FictionalDemoTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_fixed_demo_data_is_valid_normalized_and_independent(self):
        self.assertEqual(DEMO_FIELDS['business_name'], 'Fictional Home Services')
        self.assertEqual(DEMO_FIELDS['business_phone'], '(202) 555-0147')
        self.assertEqual(DEMO_FIELDS['website_url'], 'https://example.com')
        self.assertEqual(DEMO_SERVICES, ('Emergency Plumbing', 'Boiler Repair'))
        first = demo_form_data()
        first['business_name'] = 'Changed locally'
        first.setlist('services', ['Drain Cleaning'])
        second = demo_form_data()
        self.assertEqual(second['business_name'], 'Fictional Home Services')
        self.assertEqual(second.getlist('services'), list(DEMO_SERVICES))
        data, errors = validate_intake(second)
        self.assertEqual(errors, [])
        self.assertEqual(data['business_phone'], '(202) 555-0147')
        self.assertEqual(data['business_phone_canonical'], '+12025550147')
        self.assertTrue(is_approved_demo_payload(data))
        changed = dict(data)
        changed['business_name'] = 'Different Business'
        self.assertFalse(is_approved_demo_payload(changed))

    def test_demo_route_uses_shared_generator_and_prominent_notice(self):
        response = self.client.get('/demo')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('Fictional demonstration — sample information only.', html)
        self.assertIn('never published or transmitted automatically', html)
        self.assertIn('Fictional Demo Information', html)
        self.assertIn(
            'These details are fictional and are included only to demonstrate the application.',
            html,
        )
        self.assertNotIn('User-Provided Business Information', html)
        self.assertNotIn(
            'These details were supplied by the user and were not independently verified by the application.',
            html,
        )
        self.assertIn('<dt>Monthly Budget (USD)</dt><dd>$2,500.00</dd>', html)
        for value in [
                'Fictional Home Services', 'Boston, Massachusetts',
                'Boston, Cambridge, and Somerville', '(202) 555-0147',
                'Fictional demo license: DEMO-001',
                'Fictional demo insurance statement', 'https://example.com']:
            self.assertIn(value, html)
        data, errors = validate_intake(demo_form_data())
        self.assertEqual(errors, [])
        expected = summarize_plan(generate_campaign(data))
        for key, value in expected.items():
            self.assertIn(f'<strong>{value}</strong>', html)
        self.assertEqual(self.client.post('/demo').status_code, 405)

    def test_demo_exports_and_previews_receive_only_fixed_validated_fields(self):
        html = self.client.get('/demo').get_data(as_text=True)
        parser = FormParser()
        parser.feed(html)
        actions = [form['attrs'].get('action') for form in parser.forms]
        for action in ['/export', '/export/landing-pages', '/export/google-ads-editor',
                       '/preview/emergency-plumber', '/preview/boiler-repair']:
            self.assertIn(action, actions)
        for form in parser.forms:
            values = {}
            services = []
            for item in form['inputs']:
                if item.get('name') == 'services':
                    services.append(item.get('value'))
                elif item.get('name'):
                    values[item['name']] = item.get('value', '')
            self.assertEqual(services, list(DEMO_SERVICES))
            self.assertEqual(values['business_name'], DEMO_FIELDS['business_name'])
            self.assertEqual(values['website_url'], DEMO_FIELDS['website_url'])

    def test_regular_intake_and_results_are_not_labeled_as_demo(self):
        intake = self.client.get('/').get_data(as_text=True)
        self.assertIn('href="/demo"', intake)
        self.assertIn('View Fictional Demo', intake)
        self.assertNotIn('Fictional demonstration — sample information only.', intake)
        form = demo_form_data()
        form['business_name'] = 'Independent Test Business'
        normal = self.client.post('/generate', data=form)
        self.assertEqual(normal.status_code, 200)
        normal_html = normal.get_data(as_text=True)
        self.assertNotIn(
            'Fictional demonstration — sample information only.',
            normal_html,
        )
        self.assertIn('User-Provided Business Information', normal_html)
        self.assertIn(
            'These details were supplied by the user and were not independently verified by the application.',
            normal_html,
        )
        self.assertNotIn('Fictional Demo Information', normal_html)

    def test_demo_browser_preview_uses_fictional_disclosures_and_title_case(self):
        response = self.client.post('/preview/emergency-plumber', data=demo_form_data())
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        for text in [
                'Fictional demonstration — sample information only.',
                'Fictional Demo Information',
                'These details are fictional and are included only to demonstrate the application.',
                'License Information', 'Insurance Information', 'Additional Business Information',
                'This is a fictional example phone number used for demonstration only.',
                'Help with Urgent Plumbing Problems', 'About This Service', 'Service Area',
                'Service Availability', 'Service Questions', 'Business Phone',
                'Request Service — Preview Form', 'Discuss Your Emergency Plumbing Needs']:
            self.assertIn(text, html)
        self.assertNotIn('user-provided', html.lower())

    def test_demo_offline_package_uses_fictional_disclosures(self):
        response = self.client.post('/export/landing-pages', data=demo_form_data())
        self.assertEqual(response.status_code, 200)
        with ZipFile(BytesIO(response.data)) as archive:
            names = [
                INDEX_PATH,
                service_filename('Emergency Plumbing'),
                service_filename('Boiler Repair'),
                README_PATH,
            ]
            text = '\n'.join(archive.read(name).decode('utf-8') for name in names)
            index = archive.read(INDEX_PATH).decode('utf-8')
        self.assertIn('Fictional demonstration — sample information only.', index)
        self.assertIn(
            'These details are fictional and are included only to demonstrate the application.',
            index,
        )
        self.assertIn('Fictional Demo Information', text)
        self.assertIn('This is a fictional example phone number used for demonstration only.', text)
        self.assertNotIn('user-provided', text.lower())

    def test_normal_browser_preview_retains_user_provided_disclosures(self):
        form = demo_form_data()
        form['business_name'] = 'Independent Test Business'
        response = self.client.post('/preview/emergency-plumber', data=form)
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('Provided Business Information', html)
        self.assertIn('(user-provided)', html)
        self.assertIn(
            'Supplied details were provided by the user and were not independently verified by the application.',
            html,
        )
        self.assertIn(
            'This phone number was provided by the user and was not independently verified by the application.',
            html,
        )
        self.assertNotIn('Fictional Demo Information', html)


if __name__ == '__main__':
    unittest.main()
