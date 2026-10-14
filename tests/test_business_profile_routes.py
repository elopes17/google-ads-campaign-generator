from html.parser import HTMLParser
from io import BytesIO
import unittest
from zipfile import ZipFile

from app import app
from test_generator import submission


PROFILE_FIELDS = [
    'business_phone', 'license_information', 'insurance_information',
    'additional_business_information',
]


class ProfileHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms = []
        self.current = None
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form':
            self.current = {'attrs': attrs, 'inputs': []}
            self.forms.append(self.current)
        elif tag == 'input' and self.current is not None:
            self.current['inputs'].append(attrs)
        elif tag == 'a':
            self.links.append(attrs.get('href', ''))

    def handle_endtag(self, tag):
        if tag == 'form':
            self.current = None


class BusinessProfileRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def profile_form(self, goal='Phone calls', **changes):
        values = {
            'business_phone': '+1 617 555 0123',
            'license_information': 'License <ABC>',
            'insurance_information': 'Coverage & details',
            'additional_business_information': 'Locally operated',
            'primary_goal': goal,
        }
        values.update(changes)
        return submission(['Emergency Plumbing'], **values)

    def test_intake_fields_and_invalid_value_retention(self):
        html = self.client.get('/').get_data(as_text=True)
        self.assertIn('Enter only facts verified by the business.', html)
        for field, limit in [('business_phone', '30'), ('license_information', '160'),
                             ('insurance_information', '160'), ('additional_business_information', '240')]:
            self.assertIn(f'name="{field}"', html)
            self.assertIn(f'maxlength="{limit}"', html)
        self.assertIn('type="tel" id="business_phone"', html)

        form = self.profile_form(license_information='Retain <this>\u200b')
        response = self.client.post('/generate', data=form)
        self.assertEqual(response.status_code, 400)
        html = response.get_data(as_text=True)
        self.assertIn('Retain &lt;this&gt;', html)
        self.assertIn('control or formatting characters', html)

    def test_results_summary_and_all_post_forms_transport_profile(self):
        response = self.client.post('/generate', data=self.profile_form())
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('User-Provided Business Information', html)
        self.assertIn('(617) 555-0123', html)
        self.assertIn('License &lt;ABC&gt;', html)
        self.assertIn('not independently verified', html)
        parser = ProfileHTMLParser()
        parser.feed(html)
        actions = [form['attrs'].get('action') for form in parser.forms]
        self.assertIn('/export', actions)
        self.assertIn('/export/landing-pages', actions)
        self.assertIn('/preview/emergency-plumber', actions)
        for rendered in parser.forms:
            values = {item.get('name'): item.get('value') for item in rendered['inputs']}
            for field in PROFILE_FIELDS:
                self.assertIn(field, values)
            self.assertEqual(values['business_phone'], '(617) 555-0123')
            self.assertEqual(values['license_information'], 'License <ABC>')

    def test_goal_phone_cta_matrix_in_browser_and_zip(self):
        for goal, calls, forms in [
            ('Phone calls', True, False),
            ('Quote/service requests', False, True),
            ('Phone calls and quote/service requests', True, True),
        ]:
            for has_phone in [False, True]:
                with self.subTest(goal=goal, has_phone=has_phone):
                    phone = '617-555-0123' if has_phone else ''
                    form = self.profile_form(goal=goal, business_phone=phone)
                    preview = self.client.post('/preview/emergency-plumber', data=form)
                    self.assertEqual(preview.status_code, 200)
                    browser_html = preview.get_data(as_text=True)
                    archive_response = self.client.post('/export/landing-pages', data=form)
                    with ZipFile(BytesIO(archive_response.data)) as archive:
                        offline_html = archive.read('emergency-plumber.html').decode('utf-8')
                        readme = archive.read('README.txt').decode('utf-8')
                    for html in [browser_html, offline_html]:
                        parser = ProfileHTMLParser()
                        parser.feed(html)
                        tel_links = [href for href in parser.links if href.startswith('tel:')]
                        # Hero, phone-information section, and final CTA all use
                        # the same server-derived destination when calls are enabled.
                        expected = ['tel:+16175550123'] * (3 if calls and has_phone else 0)
                        self.assertEqual(tel_links, expected)
                        self.assertEqual('id="request-service"' in html, forms)
                        self.assertEqual('Call (617) 555-0123' in html, calls and has_phone)
                        if not has_phone:
                            self.assertNotIn('tel:', html)
                    if has_phone:
                        self.assertIn('was supplied by the user', readme)
                    else:
                        self.assertIn('phone remains a non-working placeholder', readme)

    def test_html_escaping_and_no_unsafe_phone_scheme(self):
        form = self.profile_form(
            license_information='<script>alert(1)</script>',
            insurance_information='<img src=x onerror=alert(2)>',
            additional_business_information='<b>Claim</b>',
        )
        for path in ['/preview/emergency-plumber', '/export/landing-pages']:
            response = self.client.post(path, data=form)
            if path.endswith('landing-pages'):
                with ZipFile(BytesIO(response.data)) as archive:
                    html = archive.read('emergency-plumber.html').decode('utf-8')
            else:
                html = response.get_data(as_text=True)
            self.assertIn('&lt;script&gt;', html)
            self.assertIn('&lt;img', html)
            self.assertNotIn('<script>', html)
            self.assertNotIn('<img', html)
            self.assertNotIn('javascript:', html.lower())
            self.assertEqual(html.count('tel:+16175550123'), 3)

    def test_invalid_exports_return_retained_intake(self):
        for path in ['/export', '/export/landing-pages', '/preview/emergency-plumber']:
            with self.subTest(path=path):
                response = self.client.post(path, data=self.profile_form(business_phone='tel:6175550123'))
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.mimetype, 'text/html')
                html = response.get_data(as_text=True)
                self.assertIn('value="tel:6175550123"', html)
                self.assertNotIn('Content-Disposition', response.headers)

    def test_independent_profile_submissions_do_not_leak(self):
        alpha = self.client.post('/preview/emergency-plumber', data=self.profile_form(
            license_information='Alpha License', additional_business_information='Alpha detail'))
        beta = self.client.post('/preview/emergency-plumber', data=self.profile_form(
            business_phone='2125550199', license_information='Beta License',
            additional_business_information='Beta detail'))
        alpha_html = alpha.get_data(as_text=True)
        beta_html = beta.get_data(as_text=True)
        self.assertIn('Alpha License', alpha_html)
        self.assertNotIn('Beta License', alpha_html)
        self.assertIn('Beta License', beta_html)
        self.assertNotIn('Alpha License', beta_html)
        self.assertIn('tel:+12125550199', beta_html)
        self.assertNotIn('tel:+12125550199', alpha_html)


if __name__ == '__main__':
    unittest.main()
