#!/usr/bin/env python3
"""Read-only diagnostics for KTV's experimental GStreamer media engine."""
import json
import platform
import sys


def inspect_gstreamer():
    result = {'available': False, 'version': None, 'elements': {}, 'missing': []}
    try:
        import gi
        gi.require_version('Gst', '1.0')
        from gi.repository import Gst
        Gst.init(None)
        result['available'] = True
        result['version'] = '.'.join(map(str, Gst.version()))
        required = {
            'playbin': 'playbin',
            'http_source': 'souphttpsrc',
            'hls_demux': 'hlsdemux',
            'mpegts_demux': 'tsdemux',
            'h264_decoder': 'avdec_h264',
            'aac_decoder': 'avdec_aac',
            'audio_convert': 'audioconvert',
            'audio_sink': 'autoaudiosink',
            'video_sink': 'autovideosink',
        }
        optional = {
            'hardware_h264': ('v4l2h264dec', 'omxh264dec', 'vaapih264dec'),
            'hardware_hevc': ('v4l2h265dec', 'vah265dec'),
            'hardware_audio': ('alsasink', 'pulsesink'),
            'alternative_h264': ('openh264dec', 'avdec_h264'),
            'alternative_hls': ('uridecodebin', 'decodebin'),
        }
        for key, factory in required.items():
            found = Gst.ElementFactory.find(factory) is not None
            result['elements'][key] = {'factory': factory, 'available': found}
            if not found:
                result['missing'].append(factory)
        for key, factories in optional.items():
            result['elements'][key] = {
                'factories': list(factories),
                'available': [name for name in factories
                              if Gst.ElementFactory.find(name) is not None],
            }
    except Exception as exc:
        result['error'] = '{}: {}'.format(type(exc).__name__, str(exc))
    return result


def main():
    try:
        from ktv_media_engine import KTVMediaEngine
        engine_import = {'available': True}
        engine = KTVMediaEngine(recovery_enabled=False)
        engine_import['playbin_available'] = engine.available
        engine.close()
    except Exception as exc:
        engine_import = {'available': False,
                         'error': '{}: {}'.format(type(exc).__name__, str(exc))}
    report = {
        'diagnostic': 'ktv-media-engine',
        'python': sys.version.split()[0],
        'architecture': platform.machine(),
        'platform': platform.platform(),
        'media_engine_import': engine_import,
        'gstreamer': inspect_gstreamer(),
        'note': 'Read-only check; no stream was opened and no system setting changed.',
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if engine_import.get('available') and report['gstreamer']['available'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
