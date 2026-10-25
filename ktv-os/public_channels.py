"""Curated starting catalog. Direct HTTPS streams on institutional domains.

Only free-to-watch channels from identifiable Brazilian broadcasters are listed.
The third-party CDN stream for SescTV is provisional until verified against the
provider's own embedded player and tested on physical hardware. No third-party
pirated listings or private addresses are used.
URLs are not a guarantee of availability, redistribution license or future
stability. Playback is explicitly user initiated, never auto-fetched at boot.
Sources: tvbrasil.ebc.com.br, canal gov/ebc.com.br, camara.leg.br.
"""
from urllib.parse import urlsplit

PUBLIC_CHANNELS=[
    {'id':'tv-brasil','name':'TV Brasil','category':'TV pública / Educação',
     'url':'https://tvbrasil-stream.ebc.com.br/index.m3u8',
     'provider':'Empresa Brasil de Comunicação (EBC)','source':'https://tvbrasil.ebc.com.br/',
     'genres':['Filmes','Documentários','Desenhos','Futebol','Notícias']},
    {'id':'canal-gov','name':'Canal Gov','category':'Informação pública',
     'url':'https://canalgov-stream.ebc.com.br/index.m3u8',
     'provider':'Empresa Brasil de Comunicação (EBC)','source':'https://canalgov.ebc.com.br/',
     'genres':['Notícias','Educação']},
    {'id':'tv-camara','name':'TV Câmara','category':'Legislativo',
     'url':'https://stream3.camara.gov.br/tv1/manifest.m3u8',
     'provider':'Câmara dos Deputados','source':'https://www.camara.leg.br/',
     'genres':['Notícias','Outros']},
    {'id':'canal-educacao','name':'Canal Educação','category':'Educação / Documentários',
     'url':'https://canaleducacao-stream.ebc.com.br/index.m3u8',
     'provider':'Empresa Brasil de Comunicação (EBC)',
     'source':'https://canaleducacao.ebc.com.br/',
     'genres':['Documentários','Educação']},
    {'id':'tv-cultura','name':'TV Cultura','category':'Cultura / Desenhos',
     'url':'https://player-tvcultura.stream.uol.com.br/live/tvcultura.m3u8',
     'provider':'Fundação Padre Anchieta / TV Cultura',
     'source':'https://cultura.uol.com.br/aovivo/',
     'genres':['Desenhos','Cultura','Filmes']},
    {'id':'sesc-tv','name':'SescTV','category':'Documentários / Cinema',
     'url':'https://slbps-ml-sambatech.akamaized.net/samba-live/2472/7424/8a00fe7cc36ac263b2c3e9324497d5ff/video/93a9920d-1b24-4c5e-a7d2-63d5489f59b5_index.m3u8',
     'provider':'SescTV (transmissão em CDN de vídeo)',
     'source':'https://sesctv.org.br/',
     'genres':['Filmes','Documentários','Cultura']},
]
ALLOWED_HOSTS={'tvbrasil-stream.ebc.com.br','canalgov-stream.ebc.com.br','stream3.camara.gov.br',
               'canaleducacao-stream.ebc.com.br','player-tvcultura.stream.uol.com.br',
               'slbps-ml-sambatech.akamaized.net'}

def validated_catalog():
    catalog=[]
    for channel in PUBLIC_CHANNELS:
        parsed=urlsplit(channel['url'])
        if parsed.scheme!='https' or parsed.hostname not in ALLOWED_HOSTS or not parsed.path.endswith('.m3u8'):
            continue
        catalog.append(dict(channel,status='experimental',note=(
            'Canal aberto de emissora identificada. Programação muda com o horário; '
            'a URL precisa ser testada na sua região. Fonte CDN do SescTV '
            'ainda exige confirmação direta com a emissora.' if channel['id']=='sesc-tv'
            else 'Link de transmissão pública; estabilidade e uso permitidos dependem da emissora.'
        )))
    return catalog

def public_channel(identifier):
    if not isinstance(identifier,str):return None
    return next((channel for channel in validated_catalog() if channel['id']==identifier),None)
