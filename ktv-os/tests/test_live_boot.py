"""Verificacoes do perfil de boot Linux Live (sem exigir root nem baixar pacotes)."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
LINUX = ROOT / 'ktv-os' / 'linux-live'

class LinuxLiveProfileTests(unittest.TestCase):
    def test_build_sources_are_complete(self):
        check = subprocess.run(
            ['bash', str(LINUX / 'build-iso.sh'), '--check'],
            text=True, capture_output=True, cwd=ROOT, timeout=10
        )
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertIn('pronto para lb config', check.stdout)

    def test_shell_syntax(self):
        for path in [
            LINUX / 'build-iso.sh',
            LINUX / 'overlay/usr/local/bin/ktv-os-session',
            LINUX / 'overlay/etc/xdg/openbox/autostart'
        ]:
            result = subprocess.run(['bash', '-n', str(path)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, path.name + ': ' + result.stderr)

    def test_real_linux_components_and_local_kiosk(self):
        packages = set((LINUX / 'packages.list.chroot').read_text().split())
        self.assertTrue({'linux-image-amd64', 'live-boot', 'live-config', 'mpv', 'udiskie',
                         'lightdm', 'openbox', 'chromium', 'python3'} <= packages)
        lightdm = (LINUX / 'overlay/etc/lightdm/lightdm.conf.d/50-ktv-os.conf').read_text()
        self.assertIn('autologin-user=user', lightdm)
        self.assertIn('user-session=openbox', lightdm)
        openbox = (LINUX / 'overlay/etc/xdg/openbox/autostart').read_text()
        self.assertIn('/usr/local/bin/ktv-os-session', openbox)
        session = (LINUX / 'overlay/usr/local/bin/ktv-os-session').read_text()
        self.assertIn('python3 launcher.py --port 8787', session)
        self.assertIn('--kiosk --app=http://127.0.0.1:8787/', session)
        self.assertNotIn('--disable-web-security', session)

    def test_local_user_state_and_iso_hybrid(self):
        launcher = (ROOT / 'ktv-os/launcher.py').read_text()
        self.assertIn("STATE = Path.home() / '.config' / 'ktv-os'", launcher)
        builder = (LINUX / 'build-iso.sh').read_text()
        self.assertIn('--binary-images iso-hybrid', builder)
        self.assertIn('--debian-installer none', builder)
        self.assertIn('config/includes.chroot', builder)
        self.assertIn('ktv-os/player.py', builder)
        self.assertIn('ktv-os/channel_store.py', builder)
        self.assertIn('lb build', builder)

if __name__ == '__main__':
    unittest.main()
