"""TV-first X11 display layout: mirror (one desktop) or HDMI-only.

All output names, modes and positions come from xrandr --query. When no
safe mode is found the current desktop is preserved. The hardware API takes a
snapshot before previews and restores it after 20 seconds if not confirmed.
"""
import re
import shutil
import subprocess

OUTPUT_RE=re.compile(r'^([A-Za-z0-9_.-]+)\s+connected(?:\s|$)')
MODE_RE=re.compile(r'^\s+(\d{3,5}x\d{3,5})(?:\s|$)')
GEOM_RE=re.compile(r'\b(\d{3,5}x\d{3,5})([+-]\d+)([+-]\d+)\b')

def outputs(raw):
    found=[]
    current=None
    for line in raw.splitlines():
        match=OUTPUT_RE.match(line)
        if match:
            geom=GEOM_RE.search(line)
            name=match.group(1)
            current={'name':name,'modes':[],'mode':geom.group(1) if geom else None,
                     'x':int(geom.group(2)) if geom else 0,
                     'y':int(geom.group(3)) if geom else 0,
                     'primary':' primary ' in line,
                     'external':name.upper().startswith(('HDMI','DP-','DISPLAYPORT'))}
            found.append(current)
            continue
        if line and not line[0].isspace():
            current=None
        if current is None:continue
        mode=MODE_RE.match(line)
        if mode:
            name=mode.group(1)
            if name not in current['modes']:current['modes'].append(name)
            if '*' in line and current['mode'] is None:current['mode']=name
    return found

def choose_mode(modes):
    if not modes:return None
    def key(mode):
        try:
            w,h=map(int,mode.split('x'))
        except ValueError:return (0,0)
        return (mode=='1920x1080',mode=='1280x720',w*h)
    return max(modes,key=key)

def layout_command(screens,target,kind):
    if kind not in ('mirror','hdmi_only'):
        raise ValueError('Modo HDMI desconhecido')
    ext=next((x for x in screens if x['name']==target and x['external']),None)
    if ext is None:
        raise ValueError('Saída HDMI/DisplayPort não encontrada')
    internal=next((x for x in screens if not x['external'] and
                   x['name'].upper().startswith(('EDP','LVDS','DSI'))),None)
    if kind=='mirror' and internal is None:
        kind='hdmi_only'
    if kind=='mirror':
        common=set(ext['modes']).intersection(internal['modes'])
        mode=choose_mode(common)
        if not mode:raise ValueError('Sem resolução comum; escolha somente TV ou mantenha o vídeo atual')
    else:
        mode=ext['mode'] if ext['mode'] in ext['modes'] else choose_mode(ext['modes'])
        if not mode:raise ValueError('Monitor HDMI não anunciou nenhuma resolução')
    args=['xrandr','--output',target,'--primary','--mode',mode,'--pos','0x0']
    for screen in screens:
        if screen['name']==target:continue
        if kind=='mirror' and screen is internal:
            args.extend(['--output',screen['name'],'--mode',mode,'--same-as',target])
        else:
            args.extend(['--output',screen['name'],'--off'])
    return args

def restore_command(screens):
    args=['xrandr']
    for screen in screens:
        args.extend(['--output',screen['name']])
        if screen['mode'] is None:
            args.append('--off')
        else:
            args.extend(['--mode',screen['mode'],'--pos',
                         '{}x{}'.format(screen['x'],screen['y'])])
            if screen['primary']:args.append('--primary')
    return args

def mirror(runner=None,which=None):
    runner=runner or subprocess.run
    which=which or shutil.which
    if not which('xrandr'):return 'xrandr indisponível'
    try:
        result=runner(['xrandr','--query'],capture_output=True,text=True,timeout=5,check=False)
        if result.returncode:return 'Falha ao consultar saídas xrandr: '+result.stderr.strip()[:100]
        screens=outputs(result.stdout)
        ext=next((x for x in screens if x['external']),None)
        if ext is None:return 'Sem HDMI detectado; tela atual preservada'
        try:
            command=layout_command(screens,ext['name'],'mirror')
        except ValueError as exc:
            # Never turn off the built-in screen without explicit user consent.
            return str(exc)+'; tela atual preservada'
        changed=runner(command,capture_output=True,text=True,timeout=8,check=False)
        return ('HDMI espelhado com sucesso' if changed.returncode==0 else
                'Falha ao espelhar: '+changed.stderr.strip()[:150])
    except (OSError,subprocess.TimeoutExpired):
        return 'Falha de driver ou tempo esgotado no xrandr; layout original preservado'

if __name__=='__main__':
    print(mirror())
