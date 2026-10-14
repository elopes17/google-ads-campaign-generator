"""Build offline landing-page ZIP downloads entirely in memory."""
from io import BytesIO
import re
import unicodedata
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from flask import current_app, render_template

from demo_data import is_approved_demo_payload
from rules_library import RULES


ZIP_MIMETYPE = 'application/zip'
ASSET_PATH = 'assets/landing_page.css'
README_PATH = 'README.txt'
INDEX_PATH = 'index.html'


def landing_pages_filename(business_name):
    """Return a bounded filename containing only portable filename characters."""
    ascii_name = unicodedata.normalize('NFKD', business_name).encode('ascii', 'ignore').decode()
    slug = re.sub(r'[^a-z0-9]+', '-', ascii_name.lower()).strip('-')
    slug = slug[:100].rstrip('-')
    if not slug:
        return 'landing-pages.zip'
    return f'{slug}-landing-pages.zip'


def service_filename(service):
    """Derive an internal filename only from the approved service rule path."""
    rule = RULES[service]
    slug = rule['path'].lstrip('/')
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug):
        raise ValueError(f'Unsafe approved service slug: {slug!r}')
    return f'{slug}.html'


def _write_text(archive, path, text):
    """Write deterministic UTF-8 text without touching the server filesystem."""
    info = ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    archive.writestr(info, text.encode('utf-8'))


def build_landing_pages_zip(data, pages):
    """Render selected page dictionaries and return a ready-to-send ZIP buffer."""
    demo_mode = is_approved_demo_payload(data)
    expected_services = [service for service in RULES if service in data['services']]
    if [page['service'] for page in pages] != expected_services:
        raise ValueError('Landing pages must match selected services in approved rule order.')

    page_links = [
        {'service': service, 'filename': service_filename(service)}
        for service in expected_services
    ]
    filenames = [link['filename'] for link in page_links]
    if len(filenames) != len(set(filenames)):
        raise ValueError('Approved service paths must produce unique filenames.')

    with current_app.open_resource('static/landing_page.css', mode='r') as css_file:
        css = css_file.read()

    buffer = BytesIO()
    with ZipFile(buffer, mode='w') as archive:
        index_html = render_template(
            'landing_page_index.html',
            business_name=data['business_name'],
            pages=page_links,
            demo_mode=demo_mode,
        )
        _write_text(archive, INDEX_PATH, index_html)
        for page, link in zip(pages, page_links):
            page_html = render_template(
                'landing_page.html',
                page=page,
                offline=True,
            )
            _write_text(archive, link['filename'], page_html)
        _write_text(archive, ASSET_PATH, css)
        _write_text(archive, README_PATH, _readme_text(data, page_links, demo_mode))
    buffer.seek(0)
    return buffer


def _readme_text(data, page_links, demo_mode=False):
    page_list = '\n'.join(f"- {page['service']}: {page['filename']}" for page in page_links)
    phone_note = (
        '- The example phone number is fictional and is included for demonstration only.'
        if demo_mode else
        f"- The business phone number {data['business_phone']} was supplied by the user and was not "
        "independently verified by the application."
        if data.get('business_phone') else
        '- No business phone number was supplied, so the phone remains a non-working placeholder.'
    )
    demo_notice = (
        '\nFICTIONAL DEMONSTRATION — SAMPLE INFORMATION ONLY\n'
        if demo_mode else ''
    )
    trust_note = (
        '- Business and trust details in this package are fictional demonstration data.'
        if demo_mode else
        '- Trust details are user-provided or remain clearly labeled placeholders.'
    )
    return f"""LOCAL LANDING-PAGE PREVIEWS
{demo_notice}

Business: {data['business_name']}

HOW TO OPEN
1. Extract the entire ZIP archive to one folder.
2. Keep index.html, the service HTML files, and the assets folder together.
3. Open index.html in a web browser. No Flask server or internet connection is required.

INCLUDED PAGES
{page_list}

LIMITATIONS
- These pages are local previews and are not published websites.
{phone_note}
{trust_note}
- A supplied phone works only for call-focused previews; placeholder phone controls do not dial.
- Request-service forms are disabled mockups. They do not send or save requests.
- No lead collection, deployment, tracking, or conversion setup is included.
- Replace placeholders only with verified business information before publishing anywhere.
"""
