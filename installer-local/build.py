"""Build a Samsung Orsay/Legacy widget ZIP, USB directory and LAN files (stdlib only)."""
import argparse
import os
from pathlib import Path
import shutil
import socket
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'tv-orsay'
RELEASE = ROOT / 'release'
FILENAME = 'KTV_0.4.2_BR_20261018.zip'
DIAGNOSTIC_FILENAME = 'KTVDiag_0.1.0_BR_20261018.zip'
DIAGNOSTIC_SOURCE = ROOT / 'tv-diagnostic'
BARE_FILENAME = 'KTVBare_0.1.0_BR_20261018.zip'
FLAT_FILENAME = 'KTVFlat_0.1.0_BR_20261018.zip'
BARE_SOURCE = ROOT / 'tv-bare'
FLAT_SOURCE = ROOT / 'tv-flat'


def guess_ip():
    """Choose a common LAN interface; may need manual override on VPN/WSL."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(('192.0.2.1', 9))
        return sock.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return '127.0.0.1'
    finally:
        sock.close()


def build(ip, port=80):
    if not ip or any(x in ip for x in ('/', '\\', ' ', '<', '>', '"', "'")):
        raise ValueError('IP invalido')
    if not (1 <= int(port) <= 65535):
        raise ValueError('Porta invalida')
    base = 'http://{}{}'.format(ip, '' if port == 80 else ':' + str(port))
    RELEASE.mkdir(exist_ok=True)
    widget_dir = RELEASE / 'Widget'
    usb_dir = RELEASE / 'usb' / 'userwidget'
    widget_dir.mkdir(parents=True, exist_ok=True)
    usb_dir.mkdir(parents=True, exist_ok=True)
    archive = widget_dir / FILENAME
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for path in sorted(SOURCE.rglob('*')):
            if not path.is_file() or path.name.endswith('.pyc'):
                continue
            name = path.relative_to(SOURCE).as_posix()
            if name == 'js/runtime-config.js':
                js = 'window.KTV_CONFIG = {server: %r, pollMs: 4000, client: \"orsay\"};\n' % base
                z.writestr(name, js)
            else:
                z.write(path, name)
    shutil.copy2(archive, usb_dir / FILENAME)
    # Publicar app de diagnostico independente, mantendo o KTV original disponivel.
    diagnostic_archive = widget_dir / DIAGNOSTIC_FILENAME
    with zipfile.ZipFile(diagnostic_archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for path in sorted(DIAGNOSTIC_SOURCE.rglob('*')):
            if not path.is_file() or path.name.endswith('.pyc'):
                continue
            name = path.relative_to(DIAGNOSTIC_SOURCE).as_posix()
            if name == 'js/runtime-config.js':
                z.writestr(name, 'window.KTV_DIAG_CONFIG = {server: %r};\n' % base)
            else:
                z.write(path, name)
    shutil.copy2(diagnostic_archive, usb_dir / DIAGNOSTIC_FILENAME)
    # A/B minimo: mesmo HTML, duas variantes de config.xml.
    # Bare usa namespace e itemtype do aplicativo Orsay Emby conhecido.
    # Flat usa o formato XML legado simplificado usado no KTV.
    for source, filename in ((BARE_SOURCE, BARE_FILENAME), (FLAT_SOURCE, FLAT_FILENAME)):
        archive_path = widget_dir / filename
        with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            for path in sorted(source.rglob('*')):
                if path.is_file():
                    z.write(path, path.relative_to(source).as_posix())
        shutil.copy2(archive_path, usb_dir / filename)
    bare_archive = widget_dir / BARE_FILENAME
    flat_archive = widget_dir / FLAT_FILENAME
    size = archive.stat().st_size
    diagnostic_size = diagnostic_archive.stat().st_size
    bare_size = bare_archive.stat().st_size
    flat_size = flat_archive.stat().st_size
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<rsp stat="ok"><list>'
           '<widget id="KTV"><title>KTV Local</title>'
           '<compression type="zip" size="{}"/>'
           '<description>Player KTV para Samsung Legacy</description>'
           '<download>{}/Widget/{}</download></widget>'
           '<widget id="KTVDiag"><title>KTVDiag</title>'
           '<compression type="zip" size="{}"/>'
           '<description>Teste minimo Samsung Legacy</description>'
           '<download>{}/Widget/{}</download></widget>'
           '<widget id="KTVBare"><title>KTVBare</title>'
           '<compression type="zip" size="{}"/>'
           '<description>Teste minimo com configuracao Samsung</description>'
           '<download>{}/Widget/{}</download></widget>'
           '<widget id="KTVFlat"><title>KTVFlat</title>'
           '<compression type="zip" size="{}"/>'
           '<description>Teste minimo com configuracao simplificada</description>'
           '<download>{}/Widget/{}</download></widget>'
           '</list></rsp>\n').format(size, base, FILENAME, diagnostic_size, base, DIAGNOSTIC_FILENAME,
                                    bare_size, base, BARE_FILENAME, flat_size, base, FLAT_FILENAME)
    (RELEASE / 'widgetlist.xml').write_text(xml, encoding='utf-8')
    return {'archive': archive, 'usb': usb_dir / FILENAME, 'xml': RELEASE / 'widgetlist.xml',
            'base': base, 'diagnostic_archive': diagnostic_archive,
            'diagnostic_usb': usb_dir / DIAGNOSTIC_FILENAME,
            'bare_archive': bare_archive, 'flat_archive': flat_archive}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Gerar app Orsay para servidor KTV')
    parser.add_argument('--ip', default=guess_ip(), help='IPv4 local do seu computador')
    parser.add_argument('--port', type=int, default=80, help='Porta da API (padrão: 80)')
    args = parser.parse_args()
    result = build(args.ip, args.port)
    print('Widget:', result['archive'])
    print('USB:', result['usb'])
    print('Sincronizacao:', result['base'] + '/widgetlist.xml')
