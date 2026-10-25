"""Curated starting catalog. Direct HTTPS streams on institutional domains.

Only channels made available by public Brazilian institutions are listed.
URLs are not a guarantee of availability, redistribution license or future
stability. Playback is explicitly user initiated, never auto-fetched at boot.
Sources: tvbrasil.ebc.com.br, canal gov/ebc.com.br, camara.leg.br.
"""
from urllib.parse import urlsplit

PUBLIC_CHANNELS=[
    {'id':'tv-brasil','name':'TV Brasil','category':'TV pública / Educação',
     'url':'https://tvbrasil-stream.ebc.com.br/index.m3u8',
     'provider':'Empresa Brasil de Comunicação (EBC)','source':'https://tvbrasil.ebc.com.br/'},
    {'id':'canal-gov','name':'Canal Gov','category':'Informação pública',
     'url':'https://canalgov-stream.ebc.com.br/index.m3u8',
     'provider':'Empresa Brasil de Comunicação (EBC)','source':'https://canalgov.ebc.com.br/'},
    {'id':'tv-camara','name':'TV Câmara','category':'Legislativo',
     'url':'https://stream3.camara.gov.br/tv1/manifest.m3u8',
     'provider':'Câmara dos Deputados','source':'https://www.camara.leg.br/'},
]
ALLOWED_HOSTS={'tvbrasil-stream.ebc.com.br','canalgov-stream.ebc.com.br','stream3.camara.gov.br'}

def validated_catalog():
    catalog=[]
    for channel in PUBLIC_CHANNELS:
        parsed=urlsplit(channel['url'])
        if parsed.scheme!='https' or parsed.hostname not in ALLOWED_HOSTS or not parsed.path.endswith('.m3u8'):
            continue
        catalog.append(dict(channel,status='experimental',note='Transmissão oficial; disponibilidade e direitos de uso devem ser verificados no site da emissora.'))
    return catalog

def public_channel(identifier):
    if not isinstance(identifier,str):return None
    return next((channel for channel in validated_catalog() if channel['id']==identifier),None)
