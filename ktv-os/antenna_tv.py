"""ISDB-Tb over-the-air receiver for Brazil. Requires Linux DVB tuner and antenna.

No IPTV scraping, Internet access, capture-card DRM bypass or privileged ops.
w_scan -ft -c BR -X generates legacy zap service names; dvbv5-zap tunes
a selected service and mpv plays the local DVB DVR character device.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import time

MAX_SCAN_BYTES=256*1024
MAX_SERVICES=180
SCAN_SECONDS=720
NAME_RE=re.compile(r'^[^\x00-\x1f\x7f:]{1,85}$')
SAFE_FIELD_RE=re.compile(r'^[A-Za-z0-9_.+-]{1,55}$')
FREQ_RE=re.compile(r'^\d{8,9}$')


class AntennaError(ValueError):
    pass


def parse_zap(text):
    """Validate and retain only usable free-to-air services from a scan."""
    if not isinstance(text,str) or len(text.encode('utf-8'))>MAX_SCAN_BYTES:
        raise AntennaError('Arquivo de busca de canais excede o limite')
    found=[]; seen=set(); lines=[]
    for line in text.splitlines():
        if not line or line.startswith('#') or len(line)>700:
            continue
        parts=line.split(':')
        # zap format: name:frequency:inversion:bandwidth:...:videoPID:audioPID:serviceID
        if len(parts)<12:
            continue
        name=parts[0].strip()
        if (not NAME_RE.fullmatch(name) or name.startswith('-') or
                not FREQ_RE.fullmatch(parts[1]) or
                not 170000000<=int(parts[1])<=810000000 or
                not all(SAFE_FIELD_RE.fullmatch(part) for part in parts[2:]) or
                len(parts)>20):
            continue
        if name.casefold() in seen:
            continue
        # PID fields are near the end of w_scan zap format; actual tuner
        # selection and PID handling remain with dvbv5-zap.
        if not any(x.isdecimal() and 16<=int(x)<=8190 for x in parts[-4:]):
            continue
        seen.add(name.casefold())
        found.append({'id':len(found),'name':name,'source':'antena','frequency':int(parts[1])})
        lines.append(line)
        if len(found)>=MAX_SERVICES:
            break
    return found, '\n'.join(lines)+'\n' if lines else ''


class AntennaTV:
    def __init__(self,state_dir,device_root='/dev/dvb',popen=None,
                 scanner=None,zapper=None,wait=None):
        self.state_dir=Path(state_dir)
        self.device_root=Path(device_root)
        self.popen=popen or subprocess.Popen
        self.scanner=scanner if scanner is not None else shutil.which('w_scan')
        self.zapper=zapper if zapper is not None else shutil.which('dvbv5-zap')
        self.wait=wait or time.sleep
        self.path=self.state_dir/'antenna_channels.conf'
        self.lock=threading.RLock()
        self.scan_process=None
        self.tune_process=None
        self.scan_state='idle'
        self.scan_error=None
        self.scanned=[]
        self.adapter=None
        self._refresh_file()

    def _hardware(self):
        for number in range(4):
            base=self.device_root/('adapter'+str(number))
            if (base/'frontend0').exists() and (base/'dvr0').exists():
                return number,base
        return None,None

    def _refresh_file(self):
        try:
            if self.path.is_symlink() or not self.path.is_file() or self.path.stat().st_size>MAX_SCAN_BYTES:
                return
            data=self.path.read_text(encoding='utf-8')
            self.scanned,_=parse_zap(data)
        except (OSError,UnicodeError,AntennaError):
            self.scanned=[]

    def available(self):
        adapter,base=self._hardware()
        return adapter is not None and bool(self.scanner and self.zapper)

    def status(self):
        with self.lock:
            adapter,base=self._hardware()
            return {
                'available':bool(adapter is not None and self.scanner and self.zapper),
                'tuner_found':adapter is not None,
                'adapter':adapter,
                'scan_state':self.scan_state,
                'scan_error':self.scan_error,
                'channels':list(self.scanned),
                'playing':self.tune_process is not None and self.tune_process.poll() is None,
                'needs_antenna':True,
                'message':('Conecte um receptor USB ISDB-Tb compativel com Linux e uma antena.'
                           if adapter is None else
                           'Instale as ferramentas w-scan e dvb-tools na ISO.'
                           if not self.scanner or not self.zapper else
                           'Receptor detectado. Busque os canais de sua regiao.'),
            }

    def start_scan(self):
        with self.lock:
            if self.scan_state=='running':
                raise AntennaError('Busca ja em andamento')
            adapter,_=self._hardware()
            if adapter is None:
                raise AntennaError('Nenhum sintonizador ISDB-Tb Linux detectado. Conecte o USB e a antena.')
            if not self.scanner or not self.zapper:
                raise AntennaError('Ferramentas de TV digital indisponiveis')
            if self.tune_process is not None and self.tune_process.poll() is None:
                raise AntennaError('Pare o canal da antena antes de buscar')
            self.scan_state='running'
            self.scan_error=None
            self.adapter=adapter
            threading.Thread(target=self._scan, args=(adapter,),daemon=True).start()
            return self.status()

    def _scan(self,adapter):
        # Buffered to a private file: never stream unbounded scan logs to UI.
        filename=None
        try:
            self.state_dir.mkdir(parents=True,exist_ok=True)
            fd,filename=tempfile.mkstemp(prefix='.ktv-scan-',dir=self.state_dir)
            os.fchmod(fd,0o600)
            with os.fdopen(fd,'wb') as sink:
                args=[self.scanner,'-ft','-c','BR','-X','-E','0','-a',str(adapter)]
                process=self.popen(args,stdin=subprocess.DEVNULL,
                                   stdout=sink,stderr=subprocess.DEVNULL)
                with self.lock:self.scan_process=process
                try: code=process.wait(timeout=SCAN_SECONDS)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                    raise AntennaError('Busca expirou apos 12 minutos')
            if code!=0:raise AntennaError('O receptor nao concluiu a busca. Confira sinal, driver e antena.')
            if Path(filename).stat().st_size>MAX_SCAN_BYTES:
                raise AntennaError('Resultado da busca excedeu tamanho permitido')
            channels,clean=parse_zap(Path(filename).read_text(encoding='utf-8',errors='replace'))
            if not channels:raise AntennaError('Nenhum canal digital detectado. Verifique antena e alcance.')
            if self.path.is_symlink():
                raise AntennaError('Arquivo de canais inseguro')
            with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',
                    dir=self.state_dir,prefix='.ktv-channels-',delete=False) as target:
                safe_path=Path(target.name)
                os.chmod(safe_path,0o600)
                try:
                    target.write(clean)
                    target.flush()
                    os.fsync(target.fileno())
                finally:
                    pass
            os.replace(safe_path,self.path)
            with self.lock:
                self.scanned=channels
                self.scan_state='ready'
                self.scan_error=None
        except (OSError,UnicodeError,AntennaError,subprocess.SubprocessError) as exc:
            with self.lock:
                self.scan_state='error'
                self.scan_error=str(exc)[:170]
        finally:
            with self.lock:self.scan_process=None
            if filename:
                try:os.unlink(filename)
                except OSError:pass

    def stop(self):
        with self.lock:
            p=self.tune_process
            self.tune_process=None
            if p is not None and p.poll() is None:
                p.terminate()
                try:p.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    p.kill()
                    p.wait(timeout=3)

    def play(self,index,player,quality='balanced',decode='default'):
        with self.lock:
            if type(index) is not int or index<0 or index>=len(self.scanned):
                raise AntennaError('Canal de antena invalido. Execute uma busca antes.')
            if self.scan_state=='running':
                raise AntennaError('Aguarde o fim da busca')
            adapter,base=self._hardware()
            if adapter is None or not self.zapper:
                raise AntennaError('Receptor USB nao disponivel')
            # No client-provided paths, names or shell interpolation.
            name=self.scanned[index]['name']
            self.stop()
            self.adapter=adapter
            args=[self.zapper,'-a',str(adapter),'-c',str(self.path),
                  '-I','zap','-r',name]
            try:
                self.tune_process=self.popen(args,stdin=subprocess.DEVNULL,
                      stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                self.wait(.7)
                if self.tune_process.poll() is not None:
                    raise AntennaError('Falha ao sintonizar. Confira sinal e permissoes do USB.')
                source=str(base/'dvr0')
                # The existing mpv opens a local Linux DVB character device.
                from player import NativePlayer
                if isinstance(player,NativePlayer):
                    return player.play(source,name,quality=quality,decode=decode)
                return player.play(source,name)
            except (OSError,RuntimeError,ValueError,AntennaError):
                self.stop()
                raise

    def close(self):
        self.stop()
        with self.lock:
            if self.scan_process is not None and self.scan_process.poll() is None:
                self.scan_process.terminate()
