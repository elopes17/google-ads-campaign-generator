import re
import unittest
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from app import app, summarize_plan
from generator import generate_campaign
from test_generator import submission
from validation import validate_intake


PROJECT_ROOT = Path(__file__).resolve().parents[1]
POST_FIELDS = {
    'business_name', 'city', 'state', 'service_area', 'monthly_budget',
    'emergency_availability', 'primary_goal', 'business_phone',
    'license_information', 'insurance_information',
    'additional_business_information', 'website_url', 'services',
}


class FormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form':
            self.current = {'attrs': attrs, 'inputs': [], 'selects': []}
            self.forms.append(self.current)
        elif tag == 'input' and self.current is not None:
            self.current['inputs'].append(attrs)
        elif tag == 'select' and self.current is not None:
            self.current['selects'].append(attrs)

    def handle_endtag(self, tag):
        if tag == 'form':
            self.current = None


class UserInterfaceContractTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_intake_groups_landmarks_skip_link_and_field_contract(self):
        html = self.client.get('/').get_data(as_text=True)
        self.assertIn('<a class="skip-link" href="#main-content">', html)
        self.assertIn('<header class="app-header"', html)
        self.assertIn('<main class="page-shell intake-page" id="main-content">', html)
        self.assertIn('<footer class="app-footer">', html)
        self.assertIn('<h2>Tell Us About the Campaign</h2>', html)
        section_headings = {
            'campaign-basics-heading': 'Campaign Basics',
            'goals-heading': 'Goals and Availability',
            'services-heading': 'Services to Advertise',
            'optional-information-heading': 'Optional Business Information',
        }
        for heading_id, heading in section_headings.items():
            self.assertIn(
                f'<section class="form-section" aria-labelledby="{heading_id}">',
                html,
            )
            self.assertIn(f'<h3 id="{heading_id}">{heading}</h3>', html)
        self.assertNotIn('<fieldset class="form-section">', html)
        self.assertIn('<fieldset class="choice-group availability-group">', html)
        self.assertIn(
            '<legend><span class="choice-legend-content">24/7 Emergency Service '
            '<span class="field-status">Required</span></span></legend>\n'
            '                <div class="choice-panel">',
            html,
        )
        self.assertIn('<fieldset class="choice-group service-choice-group">', html)
        self.assertIn(
            '<legend class="visually-hidden">Services to Advertise</legend>',
            html,
        )
        for field_id, label in {
            'business_phone': 'Business Phone Number',
            'license_information': 'License Information',
            'insurance_information': 'Insurance Information',
            'additional_business_information': 'Additional Business Information',
            'website_url': 'Business Website Base URL',
        }.items():
            self.assertIn(f'<label for="{field_id}">{label}</label>', html)
        self.assertNotIn('(optional)', html.lower())
        parser = FormParser()
        parser.feed(html)
        self.assertEqual(len(parser.forms), 1)
        form = parser.forms[0]
        self.assertEqual(form['attrs'].get('action'), '/generate')
        self.assertEqual(form['attrs'].get('method'), 'post')
        control_names = {item.get('name') for item in form['inputs'] + form['selects']}
        self.assertEqual(control_names, POST_FIELDS)
        self.assertNotIn('milestone', html.lower())

    def test_results_summary_export_payloads_landmarks_and_product_language(self):
        selected = ['Emergency Plumbing', 'Boiler Repair']
        form_data = submission(
            selected, website_url='https://example.com',
            primary_goal='Phone calls and quote/service requests',
        )
        response = self.client.post('/generate', data=form_data)
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('<a class="skip-link" href="#main-content">', html)
        self.assertIn('<header class="app-header results-header" id="top">', html)
        self.assertIn('<main class="page-shell results" id="main-content">', html)
        self.assertIn('<footer class="app-footer">', html)
        self.assertIn('Draft Campaign Plan — review before use.', html)
        self.assertIn('conversion tracking has not been configured', html)
        self.assertNotIn('milestone', html.lower())
        for visible_text in [
                'Draft Campaign Plan', 'Plan at a Glance', 'Ad Groups',
                'Negative Keywords', 'Responsive Search Ads', 'Export This Draft',
                'Excel Workbook', 'Offline Landing Pages', 'Google Ads Editor Draft',
                'Submitted Campaign Details', 'User-Provided Business Information',
                'Jump to a Section', 'Campaign Structure', 'Budget Allocation',
                'Landing Pages', 'Conversion Tracking', 'Review Notes']:
            self.assertIn(visible_text, html)
        self.assertIn('<dt>Monthly Budget (USD)</dt><dd>$2,500.01</dd>', html)

        data, errors = validate_intake(form_data)
        self.assertEqual(errors, [])
        expected = summarize_plan(generate_campaign(data))
        keys = {
            'campaigns': 'campaigns', 'ad-groups': 'ad_groups',
            'keywords': 'keywords', 'negative-keywords': 'negative_keywords',
            'responsive-search-ads': 'responsive_search_ads',
        }
        for html_key, data_key in keys.items():
            self.assertRegex(
                html,
                rf'<li data-summary="{html_key}"><strong>{expected[data_key]}</strong>',
            )

        parser = FormParser()
        parser.feed(html)
        export_actions = {'/export', '/export/landing-pages', '/export/google-ads-editor'}
        export_forms = [form for form in parser.forms
                        if form['attrs'].get('action') in export_actions]
        self.assertEqual({form['attrs']['action'] for form in export_forms}, export_actions)
        for form in export_forms:
            self.assertEqual(form['attrs'].get('method'), 'post')
            self.assertEqual({item.get('name') for item in form['inputs']}, POST_FIELDS)
            services = [item.get('value') for item in form['inputs']
                        if item.get('name') == 'services']
            self.assertEqual(services, selected)
            budget = next(item.get('value') for item in form['inputs']
                          if item.get('name') == 'monthly_budget')
            self.assertEqual(budget, '2500.01')
        self.assertGreaterEqual(html.count('role="region"'), 8)
        self.assertNotIn(
            '<p class="section-return"><a href="#top">Back to top</a> · '
            '<a href="/">Back to intake form</a></p>\n        '
            '<p class="section-return">',
            html,
        )

    def test_browser_and_offline_landing_pages_remain_accessible_and_product_facing(self):
        form_data = submission(
            ['Emergency Plumbing'], website_url='https://example.com',
            primary_goal='Phone calls and quote/service requests',
        )
        browser = self.client.post('/preview/emergency-plumber', data=form_data)
        self.assertEqual(browser.status_code, 200)
        browser_html = browser.get_data(as_text=True)
        self.assertIn('<a class="skip-link" href="#main-content">', browser_html)
        self.assertIn('<header class="site-header">', browser_html)
        self.assertIn('<main id="main-content">', browser_html)
        self.assertIn('<footer>', browser_html)
        self.assertNotIn('milestone', browser_html.lower())

        package = self.client.post('/export/landing-pages', data=form_data)
        with ZipFile(BytesIO(package.data)) as archive:
            offline_html = archive.read('emergency-plumber.html').decode('utf-8')
        self.assertIn('href="assets/landing_page.css"', offline_html)
        self.assertIn('href="index.html"', offline_html)
        self.assertNotIn('milestone', offline_html.lower())

    def test_styles_include_visible_focus_and_narrow_layout_rules(self):
        main_css = (PROJECT_ROOT / 'static' / 'style.css').read_text(encoding='utf-8')
        landing_css = (PROJECT_ROOT / 'static' / 'landing_page.css').read_text(encoding='utf-8')
        self.assertIn(':focus-visible', main_css)
        self.assertIn(':focus-visible', landing_css)
        self.assertRegex(
            main_css,
            re.compile(
                r'\.required-key, \.field-status\s*\{[^}]*'
                r'flex:\s*0 0 auto;[^}]*width:\s*max-content;[^}]*'
                r'white-space:\s*nowrap;',
                re.DOTALL,
            ),
        )
        self.assertRegex(
            main_css,
            re.compile(r'\.field-grid\s*\{[^}]*align-items:\s*start;', re.DOTALL),
        )
        self.assertRegex(
            main_css,
            re.compile(
                r'\.field-grid > \.field-group\s*\{[^}]*margin-top:\s*0;'
                r'[^}]*margin-bottom:\s*0;[^}]*padding-top:\s*0;'
                r'[^}]*align-self:\s*start;',
                re.DOTALL,
            ),
        )
        self.assertIn(
            '.field-grid > .field-group + .field-group { margin-top: 0; }',
            main_css,
        )
        self.assertRegex(
            main_css,
            re.compile(r'\.choice-group\s*\{[^}]*border:\s*0;', re.DOTALL),
        )
        self.assertRegex(
            main_css,
            re.compile(
                r'\.choice-panel\s*\{[^}]*background:\s*var\(--surface-soft\);'
                r'[^}]*border:\s*1px solid var\(--line\);',
                re.DOTALL,
            ),
        )
        self.assertRegex(main_css, re.compile(r'@media \(max-width: 650px\)'))
        self.assertRegex(landing_css, re.compile(r'@media \(max-width: 600px\)'))


if __name__ == '__main__':
    unittest.main()
