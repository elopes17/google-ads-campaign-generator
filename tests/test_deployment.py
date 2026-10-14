import ast
import unittest
from pathlib import Path

from app import app


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ProductionDeploymentTests(unittest.TestCase):
    def test_flask_debug_mode_is_explicitly_disabled(self):
        self.assertFalse(app.debug)
        tree = ast.parse((PROJECT_ROOT / 'app.py').read_text(encoding='utf-8'))
        debug_values = [
            keyword.value.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            for keyword in node.keywords
            if keyword.arg == 'debug' and isinstance(keyword.value, ast.Constant)
        ]
        self.assertTrue(debug_values)
        self.assertNotIn(True, debug_values)

    def test_render_uses_gunicorn_and_assigned_port(self):
        config = (PROJECT_ROOT / 'render.yaml').read_text(encoding='utf-8')
        for setting in [
                'runtime: python',
                'buildCommand: pip install -r requirements.txt',
                'startCommand: gunicorn app:app --bind 0.0.0.0:$PORT',
                'healthCheckPath: /',
                'autoDeployTrigger: off']:
            self.assertIn(setting, config)
        self.assertNotIn('debug', config.lower())

    def test_gunicorn_is_the_only_new_production_dependency(self):
        requirements = (PROJECT_ROOT / 'requirements.txt').read_text(encoding='utf-8').splitlines()
        self.assertEqual(requirements, [
            'Flask>=3.1,<4',
            'gunicorn>=26.0,<27',
            'openpyxl>=3.1,<4',
        ])


if __name__ == '__main__':
    unittest.main()
