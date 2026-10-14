from html.parser import HTMLParser
from io import BytesIO
from itertools import combinations, product
from pathlib import Path, PurePosixPath
import unittest
from zipfile import ZipFile

from app import app
from landing_page_export import (
    ASSET_PATH,
    INDEX_PATH,
    README_PATH,
    build_landing_pages_zip,
    landing_pages_filename,
    service_filename,
)
from landing_pages import generate_landing_pages
from rules_library import RULES
from validation import SERVICES, validate_intake
from test_generator import submission


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        self.tags.append((tag, attributes))
        if 'id' in attributes:
            self.ids.add(attributes['id'])


def parse_html(text):
    parser = LinkParser()
    parser.feed(text)
    return parser


class LandingPageExportTests(unittest.TestCase):
    def archive(self, services=None, **changes):
        data, errors = validate_intake(submission(SERVICES if services is None else services, **changes))
        self.assertEqual(errors, [])
        pages = generate_landing_pages(data)
        with app.app_context():
            payload = build_landing_pages_zip(data, pages).getvalue()
        return data, pages, ZipFile(BytesIO(payload))

    def test_exact_zip_contents_for_all_63_service_combinations(self):
        for size in range(1, 7):
            for selected in combinations(SERVICES, size):
                with self.subTest(selected=selected):
                    data, pages, archive = self.archive(list(selected))
                    page_files = [service_filename(service) for service in selected]
                    self.assertEqual(
                        archive.namelist(),
                        [INDEX_PATH, *page_files, ASSET_PATH, README_PATH],
                    )
                    self.assertEqual(len(archive.namelist()), len(set(archive.namelist())))
                    index = archive.read(INDEX_PATH).decode('utf-8')
                    positions = [index.index(f'href="{filename}"') for filename in page_files]
                    self.assertEqual(positions, sorted(positions))
                    for service, filename in zip(selected, page_files):
                        self.assertIn(f'href="{filename}"', index)
                        self.assertIn(service, index)
                    for service in SERVICES:
                        self.assertEqual(service in index, service in selected)

    def test_css_is_copied_byte_for_byte(self):
        data, pages, archive = self.archive(['Emergency Plumbing'])
        expected = Path(app.root_path, 'static', 'landing_page.css').read_bytes()
        self.assertEqual(archive.read(ASSET_PATH), expected)

    def test_all_services_goals_and_availability_render_offline(self):
        claims = ['24/7', '24 hour', 'overnight', 'day or night', 'day-or-night', 'round-the-clock']
        for service, goal, availability in product(
                SERVICES,
                ['Phone calls', 'Quote/service requests', 'Phone calls and quote/service requests'],
                ['Yes', 'No']):
            with self.subTest(service=service, goal=goal, availability=availability):
                data, pages, archive = self.archive(
                    [service], primary_goal=goal, emergency_availability=availability,
                )
                html = archive.read(service_filename(service)).decode('utf-8')
                parser = parse_html(html)
                self.assertIn('Local preview — not published.', html)
                self.assertIn('href="assets/landing_page.css"', html)
                self.assertNotIn('/static/landing_page.css', html)
                self.assertNotIn('Back to intake form', html)
                self.assertIn('href="index.html"', html)
                self.assertNotIn('Your campaign results remain in the original tab.', html)
                self.assertFalse(any(tag == 'script' for tag, attrs in parser.tags))
                calls = goal != 'Quote/service requests'
                forms = goal != 'Phone calls'
                hrefs = [attrs.get('href') for tag, attrs in parser.tags if tag == 'a']
                self.assertEqual('#phone-placeholder' in hrefs, calls)
                self.assertEqual('#request-service' in hrefs, forms)
                self.assertEqual('phone-placeholder' in parser.ids, calls)
                self.assertEqual('request-service' in parser.ids, forms)
                self.assertFalse(any(href and href.startswith('tel:') for href in hrefs))
                if availability == 'No':
                    for claim in claims:
                        self.assertNotIn(claim, html.lower())
                else:
                    self.assertIn('24/7 emergency service', html)

    def test_relative_urls_and_fragments_resolve_inside_archive(self):
        data, pages, archive = self.archive(SERVICES, primary_goal='Phone calls and quote/service requests')
        archive_names = set(archive.namelist())
        for filename in [INDEX_PATH, *[service_filename(service) for service in SERVICES]]:
            html = archive.read(filename).decode('utf-8')
            parser = parse_html(html)
            for tag, attrs in parser.tags:
                for attribute in ['href', 'src', 'action']:
                    value = attrs.get(attribute)
                    if value is None:
                        continue
                    self.assertNotIn('://', value)
                    self.assertFalse(value.startswith('//'))
                    self.assertFalse(value.startswith('/'))
                    if value.startswith('#'):
                        self.assertIn(value[1:], parser.ids)
                    else:
                        path, separator, fragment = value.partition('#')
                        self.assertIn(path, archive_names)
                        if fragment:
                            target = parse_html(archive.read(path).decode('utf-8'))
                            self.assertIn(fragment, target.ids)

    def test_disabled_forms_and_no_lead_submission(self):
        for goal in ['Quote/service requests', 'Phone calls and quote/service requests']:
            data, pages, archive = self.archive(['Drain Cleaning'], primary_goal=goal)
            html = archive.read(service_filename('Drain Cleaning')).decode('utf-8')
            parser = parse_html(html)
            self.assertFalse(any(tag == 'form' for tag, attrs in parser.tags))
            controls = [(tag, attrs) for tag, attrs in parser.tags if tag in ['input', 'textarea', 'button']]
            self.assertEqual(len(controls), 4)
            for tag, attrs in controls:
                self.assertIn('disabled', attrs)
                self.assertNotIn('name', attrs)
                if tag == 'button':
                    self.assertEqual(attrs.get('type'), 'button')
            self.assertIn('does not send or save requests', html)
        data, pages, archive = self.archive(['Drain Cleaning'], primary_goal='Phone calls')
        html = archive.read(service_filename('Drain Cleaning')).decode('utf-8')
        self.assertFalse(any(tag in ['form', 'input', 'textarea', 'button'] for tag, attrs in parse_html(html).tags))

    def test_html_escaping_checks_markup_and_url_attributes(self):
        hostile = '\"><script>alert(1)</script><img src=x onerror=alert(2)>&\''
        data, pages, archive = self.archive(
            ['Emergency Plumbing'], business_name=hostile, city=hostile,
            state=hostile, service_area=hostile,
        )
        for filename in [INDEX_PATH, service_filename('Emergency Plumbing')]:
            html = archive.read(filename).decode('utf-8')
            parser = parse_html(html)
            self.assertIn('&lt;script&gt;', html)
            self.assertFalse(any(tag in ['script', 'img'] for tag, attrs in parser.tags))
            for tag, attrs in parser.tags:
                self.assertNotIn('onerror', attrs)
                self.assertNotIn('onclick', attrs)
                for attribute in ['href', 'src', 'action']:
                    value = attrs.get(attribute)
                    if value is not None:
                        self.assertNotIn('javascript:', value.lower())

    def test_safe_download_and_internal_filenames(self):
        self.assertEqual(
            landing_pages_filename('Fictional Home Services'),
            'fictional-home-services-landing-pages.zip',
        )
        for name in ['../Acme:/\\*?"<>|\r\n', '=SUM(1,2)', 'Élite Plumbing', 'A' * 500]:
            filename = landing_pages_filename(name)
            self.assertRegex(filename, r'^[a-z0-9-]+\.zip$')
            self.assertLessEqual(len(filename), 118)
        for name in ['', '!!!', '水']:
            self.assertEqual(landing_pages_filename(name), 'landing-pages.zip')
        internal = [service_filename(service) for service in SERVICES]
        self.assertEqual(len(internal), len(set(internal)))
        for filename in internal:
            path = PurePosixPath(filename)
            self.assertEqual(len(path.parts), 1)
            self.assertNotIn('..', path.parts)
            self.assertRegex(filename, r'^[a-z0-9-]+\.html$')

    def test_readme_instructions_and_limitations(self):
        data, pages, archive = self.archive(['Emergency Plumbing', 'Boiler Repair'])
        readme = archive.read(README_PATH).decode('utf-8')
        for text in ['Extract the entire ZIP', 'Open index.html', 'No Flask server or internet connection is required',
                     'phone remains a non-working placeholder',
                     'Trust details are user-provided or remain clearly labeled placeholders',
                     'do not send or save requests', 'No lead collection, deployment, tracking']:
            self.assertIn(text, readme)
        self.assertIn('emergency-plumber.html', readme)
        self.assertIn('boiler-repair.html', readme)

    def test_export_is_deterministic_and_does_not_mutate_inputs(self):
        data, errors = validate_intake(submission(SERVICES))
        self.assertEqual(errors, [])
        pages = generate_landing_pages(data)
        data_before = repr(data)
        pages_before = repr(pages)
        with app.app_context():
            first = build_landing_pages_zip(data, pages).getvalue()
            second = build_landing_pages_zip(data, pages).getvalue()
        self.assertEqual(first, second)
        self.assertEqual(repr(data), data_before)
        self.assertEqual(repr(pages), pages_before)


if __name__ == '__main__':
    unittest.main()
