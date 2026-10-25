"""NetworkManager Wi-Fi/Ethernet controls for the local KTV OS kiosk.

Uses nmcli without shell. Passwords are passed on stdin (--ask), never
in process argv, logs or HTTP responses. Live ISO network profiles vanish
after reboot unless a separate persistent OS state is configured.
"""
import re
import shutil
import subprocess
import threading

class NetworkError(ValueError):
    pass

def split_nmcli(text):
    """Split escaped colon records from nmcli -t -e yes."""
    result, chars, escaping = [], [], False
    for ch in text:
        if escaping:
            chars.append(ch);escaping = False
        elif ch == '\\':
            escaping = True
        elif ch == ':':
            result.append(''.join(chars));chars = []
        else:
            chars.append(ch)
    if escaping:chars.append('\\')
    result.append(''.join(chars))
    return result

class NetworkManager:
    def __init__(self, runner=None, which=None):
        self.runner = runner or subprocess.run
        self.which = which or shutil.which
        self.lock = threading.RLock()
    def _run(self, args, input_data=None, timeout=10, secret=False):
        if not self.which('nmcli'):
            raise NetworkError('NetworkManager (nmcli) indisponivel')
        try:
            result=self.runner(['nmcli']+args, input=input_data, text=True,
                               capture_output=True, check=False,timeout=timeout)
        except (subprocess.TimeoutExpired,OSError):
            raise NetworkError('Tempo esgotado ou falha ao consultar NetworkManager')
        if result.returncode:
            # Do not reflect nmcli output after passing a password: it may contain
            # sensitive information. Never log credentials.
            if secret:
                raise NetworkError('Nao foi possivel conectar. Confira a senha, o sinal ou a permissao do NetworkManager')
            raise NetworkError('NetworkManager nao concluiu a operacao')
        return result.stdout
    def status(self):
        with self.lock:
            try:
                raw=self._run(['-t','-e','yes','-f','DEVICE,TYPE,STATE,CONNECTION','device','status'])
                devices=[]
                for line in raw.splitlines():
                    fields=split_nmcli(line)
                    if len(fields)>=4 and fields[1] in ('wifi','ethernet'):
                        devices.append({'name':fields[0],'kind':fields[1],'state':fields[2],
                                        'connection':fields[3]})
                radio=self._run(['radio','wifi']).strip()
                return {'available':True,'wifi_enabled':radio=='enabled','devices':devices,'error':''}
            except NetworkError as exc:
                return {'available':False,'wifi_enabled':False,'devices':[],'error':str(exc)}
    def scan(self):
        with self.lock:
            try:
                raw=self._run(['-t','-e','yes','-f','IN-USE,SSID,SIGNAL,SECURITY',
                                'device','wifi','list','--rescan','yes'],timeout=18)
                found={}
                for line in raw.splitlines():
                    fields=split_nmcli(line)
                    if len(fields)<4:continue
                    inuse,ssid,signal,security=fields[:4]
                    if not ssid or len(ssid)>64:continue
                    try:strength=max(0,min(100,int(signal)))
                    except ValueError:strength=0
                    old=found.get(ssid)
                    if old is None or strength>old['signal']:
                        found[ssid]={'ssid':ssid,'signal':strength,'secure':security not in ('','--'),
                                    'connected':inuse=='*'}
                return {'networks':sorted(found.values(),key=lambda x:(not x['connected'],-x['signal'],x['ssid'].lower()))[:45]}
            except NetworkError as exc:raise exc
    def connect(self,ssid,password):
        if not isinstance(ssid,str) or not 1<=len(ssid.encode('utf-8'))<=32 or any(ord(x)<32 for x in ssid):
            raise NetworkError('Nome da rede Wi-Fi invalido')
        if not isinstance(password,str) or len(password)>128 or '\n' in password or '\r' in password:
            raise NetworkError('Senha Wi-Fi invalida')
        with self.lock:
            args=['--ask','--wait','25','device','wifi','connect',ssid]
            # --ask reads the passphrase from stdin instead of exposing it
            # through /proc/$pid/cmdline. Open networks do not need a passphrase.
            self._run(args,input_data=(password+'\n') if password else '',
                      timeout=35,secret=True)
            return {'message':'Conexao Wi-Fi solicitada. Verifique o estado da rede.'}
    def set_wifi(self,enabled):
        if type(enabled) is not bool:raise NetworkError('Estado Wi-Fi invalido')
        with self.lock:
            self._run(['radio','wifi','on' if enabled else 'off'])
            return {'message':'Wi-Fi '+('ativado' if enabled else 'desativado')}
