"""Regression guard: Live ISO bundles all local launcher dependencies."""
import ast
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'linux-live' / 'build-iso.sh'
WORKFLOW = ROOT.parent / '.github' / 'workflows' / 'build-ktv-os-iso.yml'
LAUNCHER = ROOT / 'launcher.py'


class LiveISOBundleTests(unittest.TestCase):
    def test_launcher_local_modules_are_included_in_live_image(self):
        builder = BUILD.read_text(encoding='utf-8')
        tree = ast.parse(LAUNCHER.read_text(encoding='utf-8'))
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                name = node.module.split('.')[0]
                if (ROOT / (name + '.py')).is_file():
                    modules.add(name)
        self.assertIn('pluto_catalog', modules)
        for name in sorted(modules):
            source = '"$PROJECT_DIR/ktv-os/' + name + '.py"'
            target = 'config/includes.chroot/opt/ktv-os/' + name + '.py'
            self.assertIn(source, builder)
            self.assertIn('cp ' + source + ' ' + target, builder,
                          'ISO missing required module: ' + name)

    def test_iso_and_artifact_names_use_launcher_version(self):
        build = BUILD.read_text(encoding='utf-8')
        workflow = WORKFLOW.read_text(encoding='utf-8')
        self.assertIn('APP_VERSION="$(sed ', build)
        self.assertIn('ISO_NAME="KTV-OS-Alpha-${APP_VERSION}-amd64.iso"', build)
        self.assertIn('id: version', workflow)
        self.assertIn('KTV-OS-Alpha-${{ steps.version.outputs.version }}-amd64', workflow)
        self.assertIn('      - "ktv-os/pluto_catalog.py"', workflow)
        self.assertIn('sha256sum -c "$expected.sha256"', workflow)
        self.assertRegex(LAUNCHER.read_text(encoding='utf-8'),
                         r"(?m)^VERSION = '[0-9]+\.[0-9]+\.[0-9]+'$")

    def test_bash_check(self):
        subprocess.run(['bash', '-n', str(BUILD)], check=True)
        result = subprocess.run(['bash', str(BUILD), '--check'],
                                capture_output=True, text=True, check=True)
        self.assertIn('arquivos-base validados', result.stdout)


if __name__ == '__main__':
    unittest.main()
