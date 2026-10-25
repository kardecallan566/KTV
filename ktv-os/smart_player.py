"""KTV Smart Player: safe, explicit official-site fallback for known channels.

No DRM key extraction, cookies, playlist token transfer or arbitrary navigation.
The provider site owns authentication, licensing and access conditions.
"""
import re
from public_channels import public_channel

OFFICIAL_DESTINATIONS = {
    'pluto': {'name': 'Pluto TV', 'url': 'https://pluto.tv/br/'},
    'tv-brasil': {'name': 'TV Brasil', 'url': 'https://tvbrasil.ebc.com.br/'},
    'canal-gov': {'name': 'Canal Gov', 'url': 'https://canalgov.ebc.com.br/'},
    'tv-camara': {'name': 'TV Câmara', 'url': 'https://www.camara.leg.br/'},
    'canal-educacao': {'name': 'Canal Educação', 'url': 'https://canaleducacao.ebc.com.br/'},
    'tv-cultura': {'name': 'TV Cultura', 'url': 'https://cultura.uol.com.br/aovivo/'},
    'sesc-tv': {'name': 'SescTV', 'url': 'https://sesctv.org.br/'},
}
PLUTO_ID = re.compile(r'^[a-f0-9]{24}$')


class SmartPlayerError(ValueError):
    pass


def destination_for(kind, ident):
    """Resolve only a known catalog identity to a fixed official destination key."""
    if not isinstance(kind, str) or not isinstance(ident, str):
        raise SmartPlayerError('Canal invalido')
    if kind == 'pluto':
        if not PLUTO_ID.fullmatch(ident):
            raise SmartPlayerError('Canal Pluto TV invalido')
        return 'pluto'
    if kind == 'public':
        if not public_channel(ident) or ident not in OFFICIAL_DESTINATIONS:
            raise SmartPlayerError('Canal publico nao reconhecido')
        return ident
    # Community M3U and personal URLs have no verified official site mapping.
    return None


def options_for(kind, ident, browser_available):
    destination = destination_for(kind, ident)
    return {
        'official_available': bool(destination and browser_available),
        'official_name': OFFICIAL_DESTINATIONS[destination]['name'] if destination else None,
        'official_reason': ('Abra o site oficial no navegador. Login, regiao e DRM dependem '
                            'do provedor e do suporte do navegador.' if destination else
                            'Nao ha um site oficial verificado para este canal.'),
        'compatible_available': True,
        'drm_detected': False,
    }
