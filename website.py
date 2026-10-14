"""Validate optional website origins and construct approved service URLs."""
import ipaddress
import re
import unicodedata
from urllib.parse import urlsplit


WEBSITE_URL_MAX_LENGTH = 2048
FINAL_URL_MAX_BYTES = 2084
_HOST_LABEL = re.compile(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?')
_SERVICE_PATH = re.compile(r'/[a-z0-9]+(?:-[a-z0-9]+)*')


def _has_unsupported_character(value):
    return any(unicodedata.category(character).startswith('C') for character in value)


def normalize_website_url(value):
    """Return a normalized HTTPS origin and a list of safe validation errors."""
    raw = value or ''
    errors = []
    if len(raw) > WEBSITE_URL_MAX_LENGTH:
        errors.append(f'Business website base URL must be {WEBSITE_URL_MAX_LENGTH} characters or fewer.')
    if _has_unsupported_character(raw):
        errors.append('Business website base URL contains unsupported control or formatting characters.')
    normalized = raw.strip()
    if not normalized:
        return '', errors
    if any(character.isspace() for character in normalized):
        errors.append('Business website base URL must not contain whitespace.')
        return normalized, errors

    try:
        parsed = urlsplit(normalized)
        port = parsed.port
    except ValueError:
        errors.append('Enter a valid HTTPS business website base URL.')
        return normalized, errors

    if parsed.scheme.lower() != 'https':
        errors.append('Business website base URL must begin with https://.')
    if parsed.username is not None or parsed.password is not None:
        errors.append('Business website base URL must not contain a username or password.')
    if port is not None:
        errors.append('Business website base URL must not contain a port.')
    if parsed.query or parsed.fragment:
        errors.append('Business website base URL must not contain a query string or fragment.')
    if parsed.path not in ['', '/']:
        errors.append('Business website base URL must not contain a path.')

    hostname = parsed.hostname or ''
    if not hostname:
        errors.append('Business website base URL must include a hostname.')
        return normalized, errors
    try:
        ascii_hostname = hostname.encode('idna').decode('ascii').lower()
    except UnicodeError:
        errors.append('Business website base URL has an invalid hostname.')
        return normalized, errors

    if ascii_hostname == 'localhost' or '.' not in ascii_hostname:
        errors.append('Business website base URL must use a public domain name.')
    try:
        ipaddress.ip_address(ascii_hostname)
    except ValueError:
        pass
    else:
        errors.append('Business website base URL must not use an IP address.')
    labels = ascii_hostname.split('.')
    if (len(ascii_hostname) > 253 or any(not label or not _HOST_LABEL.fullmatch(label)
                                          for label in labels)):
        errors.append('Business website base URL has an invalid hostname.')

    if errors:
        return normalized, errors
    return f'https://{ascii_hostname}', []


def build_service_url(website_origin, service_path):
    """Append one approved-looking service path to a validated website origin."""
    normalized_origin, errors = normalize_website_url(website_origin)
    if (errors or normalized_origin != website_origin
            or not _SERVICE_PATH.fullmatch(service_path)):
        raise ValueError('Final URL inputs are not approved.')
    final_url = website_origin + service_path
    if len(final_url.encode('utf-8')) > FINAL_URL_MAX_BYTES:
        raise ValueError('Final URL exceeds the supported length.')
    return final_url
