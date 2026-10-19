"""Build a Samsung Orsay/Legacy widget ZIP, USB directory and LAN files (stdlib only)."""
import argparse
import os
from pathlib import Path
import shutil
import socket
import zipfile
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'tv-orsay'
RELEASE = ROOT / 'release'
FILENAME = 'KTV_0.4.3_BR_20261018.zip'
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


SAMSUNG_NAMESPACE = 'http://www.samsung.com/'


def verify_main_widget_archive(path):
    """Confere o ZIP Orsay antes de publicar; nao comprova compatibilidade na TV."""
    with zipfile.ZipFile(path) as archive:
        paths = archive.namelist()
        if len(paths) != len(set(paths)):
            raise ValueError('Widget contem nomes de arquivos duplicados')
        for required in ('config.xml', 'widget.info', 'index.html', 'js/app.js', 'js/runtime-config.js'):
            if required not in paths:
                raise ValueError('Widget sem arquivo obrigatorio: ' + required)
        if archive.testzip() is not None:
            raise ValueError('Widget ZIP corrompido')
        config = ET.fromstring(archive.read('config.xml'))
        if config.tag != '{' + SAMSUNG_NAMESPACE + '}widget':
            raise ValueError('config.xml sem namespace Samsung Legacy')
        ns = '{' + SAMSUNG_NAMESPACE + '}'
        name = config.find(ns + 'widgetname')
        ver = config.find(ns + 'ver')
        category = config.find(ns + 'category')
        if (name is None or name.text != 'KTV Local' or
                ver is None or ver.text != '0.403' or
                category is None or category.get('itemtype') != 'Video'):
            raise ValueError('config.xml Samsung Legacy invalido')
        for tag in ('ThumbIcon', 'BigThumbIcon', 'ListIcon', 'BigListIcon'):
            el = config.find(ns + tag)
            if el is None or not el.text or el.text not in paths:
                raise ValueError('Icone faltando: ' + tag)
        body = archive.read('index.html').decode('utf-8')
        if ('$MANAGER_WIDGET/Common/API/Widget.js' not in body or
                'KTV.start()' not in body):
            raise ValueError('Biblioteca Samsung e inicio do player ausentes')
        if 'sendReadyEvent()' not in archive.read('js/app.js').decode('utf-8'):
            raise ValueError('Player nao notifica Smart Hub')
    return True


SYNC_OPTIONS = ('all', 'KTV', 'KTVDiag', 'KTVBare', 'KTVFlat', 'reference')


def validate_reference_zip(path):
    """Validar formato basico de um ZIP fornecido pelo usuario sem executa-lo."""
    candidate = Path(path)
    if not candidate.is_file() or candidate.suffix.lower() != '.zip':
        raise ValueError('Forneca um arquivo ZIP Orsay existente e confiavel')
    if candidate.stat().st_size > 100 * 1024 * 1024:
        raise ValueError('ZIP de referencia ultrapassa 100 MB')
    try:
        with zipfile.ZipFile(candidate) as z:
            names = z.namelist()
            if len(names) > 2000 or 'config.xml' not in names or 'index.html' not in names:
                raise ValueError('ZIP Orsay exige index.html e config.xml na raiz')
            if sum(item.file_size for item in z.infolist()) > 250 * 1024 * 1024:
                raise ValueError('ZIP expande para mais de 250 MB')
            for name in names:
                if name.startswith('/') or '\\' in name or '..' in name.split('/'):
                    raise ValueError('ZIP contem caminho inseguro')
            if z.testzip() is not None:
                raise ValueError('ZIP de referencia contem arquivo corrompido')
            root = ET.fromstring(z.read('config.xml'))
            titles = [el.text.strip() for el in root.iter()
                      if el.tag.split('}')[-1] == 'widgetname' and el.text and el.text.strip()]
            title = titles[0] if titles else candidate.stem
            widget_id = re.sub('[^A-Za-z0-9_-]', '', title)[:32]
            if not widget_id:
                raise ValueError('widgetname nao valido para instalar')
            return candidate, title[:80], widget_id
    except (zipfile.BadZipFile, ET.ParseError, OSError) as exc:
        raise ValueError('ZIP/config.xml de referencia invalido: {}'.format(exc))


def build(ip, port=80, sync_only='all', reference_zip=None):
    if sync_only not in SYNC_OPTIONS:
        raise ValueError('Modo de sincronizacao invalido')
    if sync_only == 'reference' and not reference_zip:
        raise ValueError('Informe --reference-zip para o modo reference')
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
    verify_main_widget_archive(archive)
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
    choices = [
        ('KTV', 'KTV Local', archive),
        ('KTVDiag', 'KTVDiag', diagnostic_archive),
        ('KTVBare', 'KTVBare', bare_archive),
        ('KTVFlat', 'KTVFlat', flat_archive),
    ]
    if sync_only == 'reference':
        candidate, title, identity = validate_reference_zip(reference_zip)
        copied = widget_dir / candidate.name
        if candidate.resolve() != copied.resolve():
            shutil.copy2(candidate, copied)
        # Nao alterar nem recomprimir a referencia original.
        choices = [(identity, title, copied)]
    elif sync_only != 'all':
        choices = [item for item in choices if item[0] == sync_only]

    # Publicar apenas o(s) aplicativo(s) escolhido(s); manter os outros ZIPs no disco.
    root = ET.Element('rsp', {'stat': 'ok'})
    listing = ET.SubElement(root, 'list')
    for identity, title, zip_path in choices:
        widget = ET.SubElement(listing, 'widget', {'id': identity})
        ET.SubElement(widget, 'title').text = title
        ET.SubElement(widget, 'compression', {'type': 'zip', 'size': str(zip_path.stat().st_size)})
        ET.SubElement(widget, 'description').text = 'Teste local Samsung Orsay'
        ET.SubElement(widget, 'download').text = base + '/Widget/' + zip_path.name
    xml_path = RELEASE / 'widgetlist.xml'
    ET.ElementTree(root).write(xml_path, encoding='utf-8', xml_declaration=True)

    return {'archive': archive, 'usb': usb_dir / FILENAME, 'xml': xml_path,
            'base': base, 'diagnostic_archive': diagnostic_archive,
            'diagnostic_usb': usb_dir / DIAGNOSTIC_FILENAME,
            'bare_archive': bare_archive, 'flat_archive': flat_archive,
            'published_files': [zip_path.name for _, _, zip_path in choices],
            'published_titles': [title for _, title, _ in choices],
            'sync_only': sync_only}



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Gerar app Orsay para servidor KTV')
    parser.add_argument('--ip', default=guess_ip(), help='IPv4 local do seu computador')
    parser.add_argument('--port', type=int, default=80, help='Porta da API (padrão: 80)')
    parser.add_argument('--sync-only', choices=SYNC_OPTIONS, default='all', help='Sincronizar somente o aplicativo selecionado')
    parser.add_argument('--reference-zip', help='ZIP Orsay de referencia confiavel (modo reference)')
    args = parser.parse_args()
    result = build(args.ip, args.port, sync_only=args.sync_only, reference_zip=args.reference_zip)
    print('Widget:', result['archive'])
    print('USB:', result['usb'])
    print('Sincronizacao:', result['base'] + '/widgetlist.xml')
    print('Publicando:', ', '.join(result['published_titles']))
