import tempfile
import unittest
from pathlib import Path, PurePosixPath
from unittest.mock import patch
from zipfile import ZipFile

from scripts.build_release import (
    ARCHIVE_ROOT, RELEASE_NAME, ReleaseBuildError, build_release,
    collect_release_files,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ReleasePackagingTests(unittest.TestCase):
    def test_public_allowlist_excludes_local_artifacts(self):
        relative = {path.as_posix() for path, _ in
                    collect_release_files(PROJECT_ROOT, require_screenshots=False)}
        self.assertIn('README.md', relative)
        self.assertIn('campaign_reference_data.py', relative)
        self.assertIn('demo_data.py', relative)
        self.assertIn('render.yaml', relative)
        for blocked in ['.DS_Store', '.venv/', '__pycache__/', '.git/']:
            self.assertFalse(any(blocked in path for path in relative))

    def test_builder_creates_safe_archive_and_digest_in_temporary_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / RELEASE_NAME
            archive_path, digest_path = build_release(
                output, PROJECT_ROOT, require_screenshots=False,
            )
            self.assertTrue(archive_path.is_file())
            self.assertTrue(digest_path.is_file())
            self.assertRegex(digest_path.read_text(encoding='ascii'),
                             rf'^[0-9a-f]{{64}}  {RELEASE_NAME}\n$')
            with ZipFile(archive_path) as archive:
                names = archive.namelist()
                self.assertTrue(names)
                self.assertEqual(len(names), len(set(names)))
                self.assertTrue(all(name.startswith(ARCHIVE_ROOT + '/') for name in names))
                for name in names:
                    member = PurePosixPath(name)
                    self.assertFalse(member.is_absolute())
                    self.assertNotIn('..', member.parts)

    def test_final_release_requires_every_approved_screenshot(self):
        relative = {path.as_posix() for path, _ in collect_release_files(PROJECT_ROOT)}
        expected = {
            'docs/screenshots/01-intake.png',
            'docs/screenshots/02-results-summary.png',
            'docs/screenshots/03-results-ads.png',
            'docs/screenshots/04-landing-page-desktop.png',
            'docs/screenshots/05-landing-page-mobile.png',
            'docs/screenshots/06-excel-workbook.png',
            'docs/screenshots/07-editor-import-review.png',
            'docs/screenshots/08-offline-package.png',
        }
        self.assertTrue(expected.issubset(relative))
        with patch('scripts.build_release.REQUIRED_SCREENSHOTS', ('missing-approved-image.png',)):
            with self.assertRaisesRegex(ReleaseBuildError, 'Approved screenshots are required'):
                collect_release_files(PROJECT_ROOT)

    def test_release_filename_is_fixed(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ReleaseBuildError, 'Release filename must be'):
                build_release(Path(directory) / 'other.zip', PROJECT_ROOT,
                              require_screenshots=False)

    def test_public_text_omits_local_absolute_paths(self):
        home_prefix = '/' + 'Users' + '/'
        cloud_folder = 'OneDrive' + '-Personal'
        for relative, path in collect_release_files(PROJECT_ROOT, require_screenshots=False):
            if path.suffix.lower() not in {'.py', '.html', '.css', '.md'}:
                continue
            text = path.read_text(encoding='utf-8')
            self.assertNotIn(home_prefix, text, relative.as_posix())
            self.assertNotIn(cloud_folder, text, relative.as_posix())


if __name__ == '__main__':
    unittest.main()
