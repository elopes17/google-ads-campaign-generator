"""Build a stateless Google Ads Editor draft package from an existing plan."""
import csv
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO
import re
import unicodedata
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from rules_library import RULES
from website import build_service_url


ZIP_MIMETYPE = 'application/zip'
CSV_PATH = 'google-ads-editor-import.csv'
README_PATH = 'README.txt'
CAMPAIGN_NAME_LIMIT = 256
EU_POLITICAL_ADS_HEADER = 'EU political ads'
EU_POLITICAL_ADS_NO = 'No'

EDITOR_COLUMNS = [
    'Campaign', 'Campaign type', 'Networks', 'Campaign daily budget',
    'Campaign status', EU_POLITICAL_ADS_HEADER, 'Ad group', 'Ad group status',
    'Keyword', 'Type', 'Status', 'Final URL',
    *[f'Headline {number}' for number in range(1, 16)],
    *[f'Description {number}' for number in range(1, 5)],
]

POSITIVE_MATCH_TYPES = {'Broad': 'broad', 'Phrase': 'phrase', 'Exact': 'exact'}
NEGATIVE_MATCH_TYPES = {
    'Broad': 'negative broad', 'Phrase': 'negative phrase', 'Exact': 'negative exact',
}
FORMULA_PREFIXES = ('=', '+', '-', '@')


class EditorExportError(ValueError):
    """Safe, user-facing Editor export failure with no submitted value included."""


def editor_export_filename(business_name):
    ascii_name = unicodedata.normalize('NFKD', business_name).encode('ascii', 'ignore').decode()
    slug = re.sub(r'[^a-z0-9]+', '-', ascii_name.lower()).strip('-')
    slug = slug[:100].rstrip('-')
    return f'{slug}-google-ads-editor.zip' if slug else 'google-ads-editor-import.zip'


def draft_campaign_name(business_name, campaign):
    prefix = 'Proposed - '
    suffix = f' - {campaign}'
    available = CAMPAIGN_NAME_LIMIT - len(prefix) - len(suffix)
    business = business_name[:available].strip() or 'Business'
    return prefix + business + suffix


def _empty_row():
    return {column: '' for column in EDITOR_COLUMNS}


def _section(plan, section_id):
    try:
        return next(section for section in plan['sections'] if section['id'] == section_id)
    except (KeyError, StopIteration) as error:
        raise EditorExportError(f'Generated plan is missing the {section_id} section.') from error


def _daily_budget(value):
    try:
        budget = Decimal(value.replace('$', '').replace(',', ''))
    except (AttributeError, InvalidOperation) as error:
        raise EditorExportError('Campaign daily budget has an unsupported value.') from error
    if not budget.is_finite() or budget <= 0:
        raise EditorExportError('Campaign daily budget must be greater than zero for Editor export.')
    return format(budget, '.2f')


def _check_cell(field, value):
    text = str(value)
    stripped = text.lstrip()
    if stripped.startswith(FORMULA_PREFIXES):
        raise EditorExportError(f'Unsafe spreadsheet content was found in {field}.')
    if any(unicodedata.category(character).startswith('C') for character in text):
        raise EditorExportError(f'Unsupported control or formatting characters were found in {field}.')


def _validate_rows(rows):
    for row in rows:
        for field, value in row.items():
            if value != '':
                _check_cell(field, value)


def build_editor_rows(data, plan):
    """Return Editor entity rows in parent-before-child import order."""
    structure = _section(plan, 'campaign-structure')['rows']
    keyword_rows = _section(plan, 'keywords')['rows']
    negative_rows = _section(plan, 'negative-keywords')['rows']
    budget_rows = _section(plan, 'budget-allocation')['rows']

    expected_services = [service for service in RULES if service in data['services']]
    if [row[1] for row in structure] != expected_services:
        raise EditorExportError('Generated campaign structure does not match selected services.')

    original_campaigns = list(dict.fromkeys(row[0] for row in structure))
    campaign_names = {
        campaign: draft_campaign_name(data['business_name'], campaign)
        for campaign in original_campaigns
    }
    if len(set(campaign_names.values())) != len(campaign_names):
        raise EditorExportError('Generated draft campaign names are not unique.')

    budget_map = {row[0]: _daily_budget(row[2]) for row in budget_rows if row[0] != 'Total'}
    if set(budget_map) != set(original_campaigns):
        raise EditorExportError('Generated campaign budgets do not match created campaigns.')

    rows = []
    campaign_keys = set()
    for campaign in original_campaigns:
        export_name = campaign_names[campaign]
        if export_name in campaign_keys:
            raise EditorExportError('Duplicate campaign entity was generated.')
        campaign_keys.add(export_name)
        row = _empty_row()
        row.update({
            'Campaign': export_name, 'Campaign type': 'Search',
            'Networks': 'Google Search', 'Campaign daily budget': budget_map[campaign],
            'Campaign status': 'Paused', EU_POLITICAL_ADS_HEADER: EU_POLITICAL_ADS_NO,
        })
        rows.append(row)

    ad_group_keys = set()
    for campaign, service in structure:
        key = (campaign_names[campaign], service)
        if key in ad_group_keys:
            raise EditorExportError('Duplicate ad group entity was generated.')
        ad_group_keys.add(key)
        row = _empty_row()
        row.update({'Campaign': key[0], 'Ad group': service, 'Ad group status': 'Paused'})
        rows.append(row)

    positive_keys = set()
    for campaign, service, keyword, match_type, _notes in keyword_rows:
        if match_type not in POSITIVE_MATCH_TYPES:
            raise EditorExportError('Unsupported positive keyword match type.')
        editor_type = POSITIVE_MATCH_TYPES[match_type]
        key = (campaign_names[campaign], service, keyword, editor_type)
        if key in positive_keys:
            raise EditorExportError('Duplicate positive keyword entity was generated.')
        positive_keys.add(key)
        row = _empty_row()
        row.update({
            'Campaign': key[0], 'Ad group': service, 'Keyword': keyword,
            'Type': editor_type, 'Status': 'Paused',
        })
        rows.append(row)

    negative_keys = set()
    for campaign, service, keyword, match_type, _reason in negative_rows:
        if match_type not in NEGATIVE_MATCH_TYPES:
            raise EditorExportError('Unsupported negative keyword match type.')
        editor_type = NEGATIVE_MATCH_TYPES[match_type]
        key = (campaign_names[campaign], service, keyword, editor_type)
        if key in negative_keys:
            raise EditorExportError('Duplicate negative keyword entity was generated.')
        negative_keys.add(key)
        row = _empty_row()
        row.update({
            'Campaign': key[0], 'Ad group': service, 'Keyword': keyword,
            'Type': editor_type,
        })
        rows.append(row)

    ads_by_service = {ad['group']: ad for ad in plan['ads']}
    if list(ads_by_service) != expected_services or len(ads_by_service) != len(plan['ads']):
        raise EditorExportError('Generated ads do not match selected services.')
    rsa_keys = set()
    for service in expected_services:
        ad = ads_by_service[service]
        key = (campaign_names[ad['campaign']], service)
        if key in rsa_keys:
            raise EditorExportError('Duplicate responsive search ad entity was generated.')
        rsa_keys.add(key)
        headlines = ad['headlines']
        descriptions = ad['descriptions']
        if len(headlines) != 15 or len({asset['text'] for asset in headlines}) != 15:
            raise EditorExportError('Responsive search ad must contain 15 unique headlines.')
        if len(descriptions) != 4 or len({asset['text'] for asset in descriptions}) != 4:
            raise EditorExportError('Responsive search ad must contain 4 unique descriptions.')
        if any(asset['count'] != len(asset['text']) or asset['count'] > 30 for asset in headlines):
            raise EditorExportError('Responsive search ad headline exceeds its supported limit.')
        if any(asset['count'] != len(asset['text']) or asset['count'] > 90 for asset in descriptions):
            raise EditorExportError('Responsive search ad description exceeds its supported limit.')
        try:
            final_url = build_service_url(data['website_url'], RULES[service]['path'])
        except ValueError as error:
            raise EditorExportError('Final URL could not be constructed from approved values.') from error
        row = _empty_row()
        row.update({
            'Campaign': key[0], 'Ad group': service, 'Status': 'Paused',
            'Final URL': final_url,
        })
        for number, asset in enumerate(headlines, 1):
            row[f'Headline {number}'] = asset['text']
        for number, asset in enumerate(descriptions, 1):
            row[f'Description {number}'] = asset['text']
        rows.append(row)

    _validate_rows(rows)
    return rows


def build_editor_csv(rows):
    _validate_rows(rows)
    output = StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=EDITOR_COLUMNS, lineterminator='\r\n')
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode('utf-8-sig')


def _write_bytes(archive, path, payload):
    info = ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    archive.writestr(info, payload)


def editor_readme(data):
    return f"""GOOGLE ADS EDITOR DRAFT CAMPAIGN PACKAGE

Business: {data['business_name']}

This package is a draft for review. It has not been uploaded, published, enabled,
or launched. All campaigns, ad groups, positive keywords, and ads are paused.

IMPORT AND REVIEW
1. Extract this ZIP and open the intended account in Google Ads Editor.
2. Resolve any unrelated pending proposed changes before importing.
3. Choose Account > Import > From file and select {CSV_PATH}.
4. Verify that Editor recognizes every English column header.
5. Review every import error and warning, then select Review imported changes.
6. Confirm entity counts, draft campaign names, budgets, match types, ads, final URLs,
   and paused statuses. Confirm each campaign is an addition rather than an edit.
7. Keep proposed changes only if you want the draft retained in the local Editor copy.
8. Do not select Post until every setting and proposed change has been checked.

INTENTIONALLY NOT CONFIGURED
This draft intentionally does not configure location targeting, language targeting,
bidding strategy, conversion actions, tracking templates, ad schedule, or other
account-specific settings. Google Ads Editor may apply account defaults. Configure
and verify every omitted setting before posting.

URL AND CONTENT LIMITATIONS
URL validation confirms syntax only. It does not prove that the website is owned by
the user, available online, policy-compliant, or that the generated service paths
exist. Verify every destination in a browser and review all Google Ads policies.

This package does not connect to Google Ads and cannot post changes. Importing and
keeping proposed changes is not the same as posting them. Never post during a test.
"""


def build_editor_package(data, plan):
    rows = build_editor_rows(data, plan)
    buffer = BytesIO()
    with ZipFile(buffer, 'w') as archive:
        _write_bytes(archive, CSV_PATH, build_editor_csv(rows))
        _write_bytes(archive, README_PATH, editor_readme(data).encode('utf-8'))
    buffer.seek(0)
    return buffer
