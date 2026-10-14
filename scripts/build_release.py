"""Build the approved portfolio ZIP from an explicit public-file allowlist."""
from argparse import ArgumentParser
from hashlib import sha256
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RELEASE_NAME = 'google-ads-campaign-generator-portfolio-v1.0.0.zip'
ARCHIVE_ROOT = 'google-ads-campaign-generator'

ROOT_FILES = (
    '.gitignore', 'CLAUDE.md', 'LICENSE', 'README.md', 'render.yaml', 'requirements.txt',
    'app.py', 'business_profile.py', 'campaign_reference_data.py', 'demo_data.py',
    'excel_export.py', 'generator.py', 'google_ads_editor_export.py',
    'landing_page_export.py', 'landing_page_rules.py', 'landing_pages.py',
    'locations.py', 'rules_library.py', 'validation.py', 'website.py',
)

PUBLIC_DIRECTORIES = {
    'docs': {'.md', '.png'},
    'scripts': {'.py'},
    'static': {'.css'},
    'templates': {'.html'},
    'tests': {'.py'},
}

REQUIRED_SCREENSHOTS = (
    '01-intake.png', '02-results-summary.png', '03-results-ads.png',
    '04-landing-page-desktop.png', '05-landing-page-mobile.png',
    '06-excel-workbook.png', '07-editor-import-review.png',
    '08-offline-package.png',
)


class ReleaseBuildError(ValueError):
    """Raised when release inputs fail the public-package checks."""


def _validate_relative_path(path):
    pure = PurePosixPath(path.as_posix())
    if pure.is_absolute() or '..' in pure.parts:
        raise ReleaseBuildError('Release paths must remain inside the project.')


def collect_release_files(root=PROJECT_ROOT, require_screenshots=True):
    """Return sorted allowlisted files and reject missing or unsafe inputs."""
    root = Path(root).resolve()
    files = []
    for relative in ROOT_FILES:
        path = root / relative
        if not path.is_file():
            raise ReleaseBuildError(f'Required release file is missing: {relative}')
        files.append(path)

    for directory, suffixes in PUBLIC_DIRECTORIES.items():
        base = root / directory
        if not base.is_dir():
            raise ReleaseBuildError(f'Required release directory is missing: {directory}')
        for path in base.rglob('*'):
            if path.is_symlink():
                raise ReleaseBuildError(f'Symlinks are not allowed in releases: {path.name}')
            if path.is_file() and path.suffix.lower() in suffixes:
                files.append(path)

    if require_screenshots:
        missing = [name for name in REQUIRED_SCREENSHOTS
                   if not (root / 'docs' / 'screenshots' / name).is_file()]
        if missing:
            raise ReleaseBuildError(
                'Approved screenshots are required before release: ' + ', '.join(missing)
            )

    unique = {}
    for path in files:
        relative = path.resolve().relative_to(root)
        _validate_relative_path(relative)
        unique[relative.as_posix()] = path
    return [(Path(relative), unique[relative]) for relative in sorted(unique)]


def build_release(output, root=PROJECT_ROOT, require_screenshots=True):
    """Create the release ZIP and adjacent SHA-256 file."""
    output = Path(output)
    if output.name != RELEASE_NAME:
        raise ReleaseBuildError(f'Release filename must be {RELEASE_NAME}.')
    output.parent.mkdir(parents=True, exist_ok=True)
    files = collect_release_files(root, require_screenshots=require_screenshots)
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        for relative, source in files:
            member = PurePosixPath(ARCHIVE_ROOT) / PurePosixPath(relative.as_posix())
            info = ZipInfo(member.as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes())

    digest_path = output.with_suffix('.sha256')
    digest_path.write_text(f'{sha256(output.read_bytes()).hexdigest()}  {output.name}\n',
                           encoding='ascii')
    return output, digest_path


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path,
                        default=PROJECT_ROOT / 'dist' / RELEASE_NAME)
    args = parser.parse_args()
    output, digest = build_release(args.output)
    print(output)
    print(digest)


if __name__ == '__main__':
    main()
