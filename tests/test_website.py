import unittest

from test_generator import submission
from validation import validate_intake
from website import build_service_url, normalize_website_url


class WebsiteValidationTests(unittest.TestCase):
    def test_blank_is_optional_and_existing_generation_remains_valid(self):
        data, errors = validate_intake(submission())
        self.assertEqual(errors, [])
        self.assertEqual(data['website_url'], '')

    def test_valid_origins_are_normalized(self):
        cases = {
            'https://example.com': 'https://example.com',
            ' HTTPS://WWW.Example.COM/ ': 'https://www.example.com',
            'https://services.example.co.uk': 'https://services.example.co.uk',
            'https://bücher.example': 'https://xn--bcher-kva.example',
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                normalized, errors = normalize_website_url(value)
                self.assertEqual(errors, [])
                self.assertEqual(normalized, expected)

    def test_invalid_origins(self):
        invalid = [
            'http://example.com', 'javascript:alert(1)', 'https://user:pass@example.com',
            'https://localhost', 'https://127.0.0.1', 'https://[::1]',
            'https://example.com:8443', 'https://example.com/base',
            'https://example.com?source=ads', 'https://example.com/#contact',
            'https://example com', 'https://-bad.example', 'https://bad-.example',
            'https://example', 'example.com',
        ]
        for value in invalid:
            with self.subTest(value=value):
                normalized, errors = normalize_website_url(value)
                self.assertTrue(errors)

    def test_length_and_invisible_characters(self):
        normalized, errors = normalize_website_url('https://' + 'a' * 2041)
        self.assertTrue(any('2048' in error for error in errors))
        for character in ['\x00', '\n', '\u200b', '\u202e']:
            with self.subTest(character=repr(character)):
                normalized, errors = normalize_website_url('https://example.com' + character)
                self.assertTrue(any('control or formatting' in error for error in errors))

    def test_service_url_requires_safe_inputs(self):
        self.assertEqual(
            build_service_url('https://example.com', '/emergency-plumber'),
            'https://example.com/emergency-plumber',
        )
        for origin, path in [
            ('http://example.com', '/emergency-plumber'),
            ('https://EXAMPLE.com', '/emergency-plumber'),
            ('https://example.com/', '/emergency-plumber'),
            ('https://example.com?next=', '/emergency-plumber'),
            ('https://example.com', 'emergency-plumber'),
            ('https://example.com', '/../admin'),
            ('https://example.com', '/service?x=1'),
        ]:
            with self.subTest(origin=origin, path=path):
                with self.assertRaises(ValueError):
                    build_service_url(origin, path)


if __name__ == '__main__':
    unittest.main()
