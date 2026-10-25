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
        self.assertTrue({'linux-image-amd64', 'live-boot', 'live-config', 'mpv', 'udiskie', 'zenity', 'pulseaudio-utils', 'cec-utils',
                         'lightdm', 'openbox', 'chromium', 'python3', 'polkitd'} <= packages)
        lightdm = (LINUX / 'overlay/etc/lightdm/lightdm.conf.d/50-ktv-os.conf').read_text()
        self.assertIn('autologin-user=user', lightdm)
        self.assertIn('user-session=openbox', lightdm)
        openbox = (LINUX / 'overlay/etc/xdg/openbox/autostart').read_text()
        self.assertIn('/usr/local/bin/ktv-os-session', openbox)
        session = (LINUX / 'overlay/usr/local/bin/ktv-os-session').read_text()
        self.assertIn('python3 launcher.py --port 8787', session)
        self.assertIn('--kiosk --app=http://127.0.0.1:8787/', session)
        self.assertIn('python3 display_layout.py', session)
        self.assertIn('export KTV_OS_LIVE=1', session)
        self.assertNotIn('--disable-web-security', session)

    def test_gpu_boot_recovery_is_opt_in_and_bounded(self):
        session = (LINUX / 'overlay/usr/local/bin/ktv-os-session').read_text()
        self.assertIn('ktv[.]safe=1', session)
        self.assertIn('if (( SAFE_BOOT ))', session)
        self.assertIn('timeout 16s python3 display_layout.py', session)
        self.assertIn('browser_safe="$SAFE_BOOT"', session)
        self.assertIn('browser_args+=(--disable-gpu --disable-gpu-compositing', session)
        self.assertIn('crashes >= 2 && browser_safe == 0', session)
        self.assertIn('crashes >= 5', session)
        self.assertNotIn('pci=noaer', session)
        self.assertNotIn('--no-sandbox', session)
        diagnostics = (LINUX / 'overlay/usr/local/bin/ktv-os-diagnostics').read_text()
        self.assertIn('journalctl -k -b', diagnostics)
        self.assertIn('lspci -nn -s 01:00.0', diagnostics)
        self.assertIn('systemctl is-active lightdm', diagnostics)
        self.assertIn('ktv-os-session', (LINUX / 'overlay/etc/xdg/openbox/autostart').read_text())
        for filename in ('ktv-os-session', 'ktv-os-diagnostics'):
            script = LINUX / 'overlay/usr/local/bin' / filename
            result = subprocess.run(['bash', '-n', str(script)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, filename + ': ' + result.stderr)

    def test_local_user_state_and_iso_hybrid(self):
        launcher = (ROOT / 'ktv-os/launcher.py').read_text()
        self.assertIn("STATE = Path.home() / '.config' / 'ktv-os'", launcher)
        builder = (LINUX / 'build-iso.sh').read_text()
        self.assertIn('--binary-images iso-hybrid', builder)
        self.assertIn('--debian-installer none', builder)
        self.assertIn('config/includes.chroot', builder)
        self.assertIn('ktv-os/player.py', builder)
        self.assertIn('ktv-os/channel_store.py', builder)
        self.assertIn('ktv-os/persistence.py', builder)
        self.assertIn('ktv-os/hardware.py', builder)
        self.assertIn('ktv-os/cec_bridge.py', builder)
        self.assertIn('ktv-os/network.py', builder)
        self.assertIn('ktv-os/display_layout.py', builder)
        self.assertIn('ktv-os/system_actions.py', builder)
        self.assertIn('ktv-os/public_channels.py', builder)
        self.assertIn('timeout 30', builder)
        self.assertIn('set timeout=3', builder)
        self.assertIn('config/hooks/live', builder)
        self.assertIn('ktv-os-diagnostics', builder)
        self.assertIn('lb build', builder)

if __name__ == '__main__':
    unittest.main()
