import csv
from copy import deepcopy
from io import BytesIO, TextIOWrapper
from itertools import combinations, product
import unittest
from zipfile import ZipFile

from generator import generate_campaign
from google_ads_editor_export import (
    CSV_PATH, EDITOR_COLUMNS, EU_POLITICAL_ADS_HEADER, EU_POLITICAL_ADS_NO,
    README_PATH, EditorExportError,
    build_editor_csv, build_editor_package, build_editor_rows, draft_campaign_name,
    editor_export_filename,
)
from rules_library import RULES
from test_generator import submission
from validation import SERVICES, validate_intake


class GoogleAdsEditorExportTests(unittest.TestCase):
    def data_and_plan(self, services=None, **changes):
        changes.setdefault('website_url', 'https://www.example.com/')
        data, errors = validate_intake(submission(SERVICES if services is None else services, **changes))
        self.assertEqual(errors, [])
        return data, generate_campaign(data)

    @staticmethod
    def groups(rows):
        return {
            'campaigns': [row for row in rows if row['Campaign type']],
            'ad_groups': [row for row in rows if row['Ad group status']],
            'positive': [row for row in rows if row['Keyword'] and not row['Type'].startswith('negative ')],
            'negative': [row for row in rows if row['Keyword'] and row['Type'].startswith('negative ')],
            'rsa': [row for row in rows if row['Headline 1']],
        }

    def test_all_combinations_goals_availability_and_phone_presence(self):
        goals = ['Phone calls', 'Quote/service requests', 'Phone calls and quote/service requests']
        for size in range(1, 7):
            for selected in combinations(SERVICES, size):
                for goal, availability, phone in product(
                        goals, ['Yes', 'No'], ['', '6175550123']):
                    with self.subTest(
                            selected=selected, goal=goal,
                            availability=availability, phone=bool(phone)):
                        data, plan = self.data_and_plan(
                            list(selected), primary_goal=goal,
                            emergency_availability=availability,
                            business_phone=phone,
                        )
                        rows = build_editor_rows(data, plan)
                        groups = self.groups(rows)
                        expected_campaigns = len({RULES[service]['campaign'] for service in selected})
                        self.assertEqual(len(groups['campaigns']), expected_campaigns)
                        self.assertEqual(len(groups['ad_groups']), len(selected))
                        self.assertEqual(len(groups['positive']), len(plan['sections'][1]['rows']))
                        self.assertEqual(len(groups['negative']), len(plan['sections'][2]['rows']))
                        self.assertEqual(len(groups['rsa']), len(selected))
                        self.assertEqual(
                            len(rows), expected_campaigns + len(selected) * 2
                            + len(plan['sections'][1]['rows']) + len(plan['sections'][2]['rows']),
                        )
                        self.assertTrue(all(row['Campaign status'] == 'Paused'
                                            for row in groups['campaigns']))
                        self.assertTrue(all(row['Ad group status'] == 'Paused'
                                            for row in groups['ad_groups']))
                        self.assertTrue(all(row['Status'] == 'Paused'
                                            for row in groups['positive'] + groups['rsa']))
                        self.assertTrue(all(row['Status'] == '' for row in groups['negative']))
                        for name in ['campaigns', 'ad_groups', 'positive', 'negative', 'rsa']:
                            entities = groups[name]
                            self.assertEqual(len(entities), len({tuple(row.items()) for row in entities}))

    def test_focused_rsa_shape_assets_and_classification(self):
        data, plan = self.data_and_plan(SERVICES)
        self.assertNotIn('Ad type', EDITOR_COLUMNS)
        rsa_rows = self.groups(build_editor_rows(data, plan))['rsa']
        self.assertEqual(len(rsa_rows), 6)
        for service, row in zip(SERVICES, rsa_rows):
            self.assertTrue(row['Campaign'].startswith('Proposed - Acme Home Services - '))
            self.assertEqual(row['Ad group'], service)
            self.assertEqual(row['Status'], 'Paused')
            self.assertEqual(row['Final URL'], 'https://www.example.com' + RULES[service]['path'])
            headlines = [row[f'Headline {number}'] for number in range(1, 16)]
            descriptions = [row[f'Description {number}'] for number in range(1, 5)]
            self.assertEqual(len(headlines), 15)
            self.assertEqual(len(set(headlines)), 15)
            self.assertEqual(len(descriptions), 4)
            self.assertEqual(len(set(descriptions)), 4)
            self.assertTrue(all(len(text) <= 30 for text in headlines))
            self.assertTrue(all(len(text) <= 90 for text in descriptions))
            self.assertEqual(row['Keyword'], '')
            self.assertEqual(row['Type'], '')
            for setting in ['Campaign type', 'Networks', 'Campaign daily budget',
                            'Campaign status', 'Ad group status']:
                self.assertEqual(row[setting], '')

    def test_keyword_types_budgets_and_draft_names(self):
        data, plan = self.data_and_plan(SERVICES, monthly_budget='2500.01')
        groups = self.groups(build_editor_rows(data, plan))
        self.assertEqual([row['Campaign daily budget'] for row in groups['campaigns']], ['41.12', '41.12'])
        self.assertTrue(all(row['Campaign type'] == 'Search' for row in groups['campaigns']))
        self.assertTrue(all(row['Networks'] == 'Google Search' for row in groups['campaigns']))
        self.assertLessEqual(len(draft_campaign_name('A' * 500, 'Plumbing Services')), 256)
        self.assertEqual({row['Type'] for row in groups['positive']}, {'phrase', 'exact'})
        self.assertEqual(
            {row['Type'] for row in groups['negative']},
            {'negative broad', 'negative phrase'},
        )

    def test_eu_political_ads_declaration_is_campaign_only(self):
        data, plan = self.data_and_plan(SERVICES)
        rows = build_editor_rows(data, plan)
        groups = self.groups(rows)
        self.assertIn(EU_POLITICAL_ADS_HEADER, EDITOR_COLUMNS)
        self.assertEqual(EU_POLITICAL_ADS_HEADER, 'EU political ads')
        self.assertEqual(EU_POLITICAL_ADS_NO, 'No')
        self.assertEqual(
            [row[EU_POLITICAL_ADS_HEADER] for row in groups['campaigns']],
            [EU_POLITICAL_ADS_NO, EU_POLITICAL_ADS_NO],
        )
        non_campaign_rows = [row for row in rows if not row['Campaign type']]
        self.assertTrue(non_campaign_rows)
        self.assertTrue(all(row[EU_POLITICAL_ADS_HEADER] == '' for row in non_campaign_rows))

    def test_csv_encoding_escaping_and_archive(self):
        data, plan = self.data_and_plan(
            ['Drain Cleaning'], business_name='Élite, "Home" Services',
        )
        first = build_editor_package(data, plan).getvalue()
        second = build_editor_package(data, plan).getvalue()
        self.assertEqual(first, second)
        with ZipFile(BytesIO(first)) as archive:
            self.assertEqual(archive.namelist(), [CSV_PATH, README_PATH])
            payload = archive.read(CSV_PATH)
            self.assertTrue(payload.startswith(b'\xef\xbb\xbf'))
            self.assertIn(b'\r\n', payload)
            with self.assertRaises(UnicodeDecodeError):
                payload.decode('ascii')
            reader = csv.DictReader(TextIOWrapper(BytesIO(payload), encoding='utf-8-sig', newline=''))
            parsed = list(reader)
            self.assertEqual(reader.fieldnames, EDITOR_COLUMNS)
            self.assertTrue(any('Élite, "Home" Services' in row['Campaign'] for row in parsed))
            readme = archive.read(README_PATH).decode('utf-8')
        for warning in [
            'location targeting', 'language targeting', 'bidding strategy',
            'conversion actions', 'tracking templates', 'ad schedule',
            'account-specific settings', 'may apply account defaults',
            'does not prove that the website is owned', 'Do not select Post',
        ]:
            self.assertIn(warning, readme)

    def test_formula_content_is_rejected_without_echoing_value(self):
        for prefix in ['=', '+', '-', '@']:
            with self.subTest(prefix=prefix):
                data, plan = self.data_and_plan(business_name=prefix + 'SUM(1,2)')
                with self.assertRaisesRegex(EditorExportError, r'Headline \d+') as caught:
                    build_editor_rows(data, plan)
                self.assertNotIn('SUM(1,2)', str(caught.exception))

        unsafe_row = {column: '' for column in EDITOR_COLUMNS}
        unsafe_row['Keyword'] = '=1+1'
        with self.assertRaisesRegex(EditorExportError, 'Keyword') as caught:
            build_editor_csv([unsafe_row])
        self.assertNotIn('=1+1', str(caught.exception))

    def test_duplicates_unsupported_values_and_zero_daily_budget_are_rejected(self):
        data, plan = self.data_and_plan(['Emergency Plumbing'])
        duplicate = deepcopy(plan)
        duplicate['sections'][1]['rows'].append(list(duplicate['sections'][1]['rows'][0]))
        with self.assertRaisesRegex(EditorExportError, 'Duplicate positive keyword'):
            build_editor_rows(data, duplicate)
        unsupported = deepcopy(plan)
        unsupported['sections'][1]['rows'][0][3] = 'Unknown'
        with self.assertRaisesRegex(EditorExportError, 'Unsupported positive'):
            build_editor_rows(data, unsupported)
        tiny_data, tiny_plan = self.data_and_plan(['Emergency Plumbing'], monthly_budget='0.01')
        with self.assertRaisesRegex(EditorExportError, 'greater than zero'):
            build_editor_rows(tiny_data, tiny_plan)

    def test_safe_filenames(self):
        self.assertEqual(
            editor_export_filename('Fictional Home Services'),
            'fictional-home-services-google-ads-editor.zip',
        )
        for name in ['../Acme:/\\*?"<>|\r\n', '=SUM(1,2)', 'Élite Plumbing', 'A' * 500]:
            filename = editor_export_filename(name)
            self.assertRegex(filename, r'^[a-z0-9-]+\.zip$')
            self.assertLessEqual(len(filename), 122)
        for name in ['', '!!!', '水']:
            self.assertEqual(editor_export_filename(name), 'google-ads-editor-import.zip')


if __name__ == '__main__':
    unittest.main()
