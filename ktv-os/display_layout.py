"""Mirror HDMI TV and laptop instead of creating an extended X11 desktop.

Only modes advertised by *both* displays are used. If no common mode,
keep the current layout (do not blank the user's only recovery screen).
Runs once at graphical session startup, no firmware/BIOS changes.
"""
import re
import shutil
import subprocess
import sys

OUTPUT_RE=re.compile(r'^([A-Za-z0-9_.-]+)\s+connected(?:\s|$)')
MODE_RE=re.compile(r'^\s+(\d{3,5}x\d{3,5})\s+')

def outputs(raw):
    found=[]
    for line in raw.splitlines():
        m=OUTPUT_RE.match(line)
        if m:
            found.append({'name':m.group(1),'modes':[]})
            continue
        if not found:continue
        m=MODE_RE.match(line)
        if m and m.group(1) not in found[-1]['modes']:
            found[-1]['modes'].append(m.group(1))
    return found

def mirror(runner=None,which=None):
    runner=runner or subprocess.run
    which=which or shutil.which
    if not which('xrandr'):
        return 'xrandr nao encontrado'
    try:
        query=runner(['xrandr','--query'],capture_output=True,text=True,timeout=5,check=False)
        if query.returncode:return 'Erro xrandr ao consultar monitores'
        monitors=outputs(query.stdout)
        hdmi=next((x for x in monitors if x['name'].upper().startswith(('HDMI','DP-'))),None)
        internal=next((x for x in monitors if x['name'].upper().startswith(('EDP','LVDS','DSI'))),None)
        if not hdmi:return 'Sem HDMI conectado: configuracao atual preservada'
        if not internal:
            r=runner(['xrandr','--output',hdmi['name'],'--primary','--auto','--pos','0x0'],
                     capture_output=True,text=True,timeout=8,check=False)
            return 'HDMI primario (tela unica)' if r.returncode==0 else 'HDMI nao configurado'
        common=set(hdmi['modes']).intersection(internal['modes'])
        if not common:
            return 'Sem resolucao comum HDMI/painel: layout preservado para recuperacao'
        def priority(mode):
            w,h=map(int,mode.split('x'))
            return (mode=='1920x1080',mode=='1280x720',w*h)
        mode=max(common,key=priority)
        result=runner(['xrandr','--output',hdmi['name'],'--primary','--mode',mode,'--pos','0x0',
                       '--output',internal['name'],'--mode',mode,'--same-as',hdmi['name']],
                      capture_output=True,text=True,timeout=8,check=False)
        return ('Espelhamento HDMI e notebook em '+mode) if result.returncode==0 else ('Falha ao espelhar HDMI; layout anterior preservado')
    except (OSError,subprocess.TimeoutExpired) as exc:
        return 'Nao foi possivel espelhar a tela: '+str(exc)

if __name__=='__main__':
    print(mirror())
