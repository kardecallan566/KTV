"""KTV integrated TV player: native streams and provider-published embed endpoints.

Only explicitly published player widgets may be placed inside KTV's UI.
Provider ads, player controls, attribution and access rules remain untouched.
No HTML scraping, URL rewriting, iframe clickjacking or DRM circumvention.
"""
import re
from public_channels import public_channel

PLUTO_ID = re.compile(r'^[a-f0-9]{24}$')

# Explicitly offered iframe endpoints, documented by their broadcasters.
# TV Brasil: https://aovivo.ebc.com.br/
# TV Cultura: https://culturaplay.tvcultura.com.br/channels/14-01-tv-cultura-ao-vivo
EMBED_PLAYERS = {
    'tv-brasil': {
        'name': 'TV Brasil · EBC',
        'url': 'https://aovivo.ebc.com.br/embed-tvbrasil.html',
    },
    'tv-cultura': {
        'name': 'TV Cultura · Cultura Play',
        'url': 'https://culturaplay.tvcultura.com.br/channels/14/embed',
    },
}
# Deny any iframe src supplied by a client. Only these constant URLs may render.
EMBED_URLS = frozenset(item['url'] for item in EMBED_PLAYERS.values())
LIVE_TV_IDS = ('tv-brasil','canal-gov','tv-camara','canal-educacao','tv-cultura')


class SmartPlayerError(ValueError):
    pass


def embed_for(kind, ident):
    if not isinstance(kind,str) or not isinstance(ident,str):
        raise SmartPlayerError('Canal invalido')
    if kind == 'public':
        if not public_channel(ident):
            raise SmartPlayerError('Canal publico nao reconhecido')
        return EMBED_PLAYERS.get(ident)
    if kind == 'pluto':
        if not PLUTO_ID.fullmatch(ident):
            raise SmartPlayerError('Identificador Pluto TV invalido')
        # Pluto does not grant generic app embedding in its terms.
        return None
    if kind in ('community','channel'):
        # Community M3U is not proof of permission to embed a player.
        return None
    raise SmartPlayerError('Tipo de canal invalido')


def options_for(kind, ident, browser_available=None):
    """browser_available is accepted for backward-compatible call signatures."""
    player=embed_for(kind,ident)
    return {
        'embed_available': bool(player),
        'embed_url': player['url'] if player else None,
        'embed_provider': player['name'] if player else None,
        'message': ('Player incorporavel disponibilizado pela emissora. '
                    'Anuncios do provedor e regras de acesso permanecem.' if player else
                    'Nao existe player incorporavel autorizado para este canal. '
                    'Experimente mpv normal ou modo compativel.'),
        'compatible_available': True,
        'drm_detected': False,
    }


def live_tv_listing():
    return [{'id': ident,
             'name': public_channel(ident)['name'],
             'kind': 'public',
             'embed_available': ident in EMBED_PLAYERS}
            for ident in LIVE_TV_IDS if public_channel(ident)]
