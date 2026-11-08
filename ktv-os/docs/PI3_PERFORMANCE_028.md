# KTV OS 0.28 — Raspberry Pi performance and thermal monitoring

## What changed
- Adds `performance_monitor.py`, a lightweight read-only sampler for CPU utilization, CPU frequency, thermal-zone temperature and RAM usage.
- Optionally reads `vcgencmd get_throttled` (cached for 15 seconds) to expose current and historical undervoltage, frequency-cap, throttling and soft-temperature flags.
- Exposes the readings at `GET /api/performance` and shows them on the home screen. The browser refreshes every 30 seconds; the endpoint itself reads procfs/sysfs and does not change system settings.
- Reports the detected Pi 3 playback profile in `/api/status`. On Raspberry Pi 3, the UI starts in Economy mode, asking HLS playlists for their lowest available variant. The user can still choose Balanced or Best.
- Does **not** force a hardware decoder, change CPU governor, overclock, or dynamically restart channels. Those changes need measurements and per-stream testing first.

## Reading the indicators
- Temperature `>=75 °C`: hot; `>=80 °C`: critical indicator. These are KTV alert bands, not a replacement for firmware thermal protection.
- `vcgencmd` flags are cumulative as well as current; historical flags can remain after cooling/reboot cycles.
- CPU percentage is a delta between samples. The first sample may show `--`.
- Missing sensor/firmware tools are reported as unavailable; telemetry must not crash playback.

## Thermal troubleshooting on Raspberry Pi 3
1. Keep the board ventilated; use a heatsink/case airflow if appropriate and inspect dust/blocked vents.
2. While a channel is playing, observe temperature, CPU, RAM and throttling flags in the home screen.
3. Compare the same channel in Economy and Balanced. HLS can offer smaller variants; direct MPEG-TS cannot be resized by this setting.
4. If temperature climbs and throttling flags appear, test a different channel/codec and inspect power supply/USB devices. Do not overclock.
5. Record the channel URL's host (never paste signed/tokenized URLs), codec, resolution, temperature and drop counters before changing decoder flags.

## SSH quick checks
```bash
vcgencmd measure_temp
vcgencmd get_throttled
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq
free -h
```

KTV does not claim that mpv telemetry proves the physical HDMI pixels or audible output. Metrics are diagnostic proxies.
