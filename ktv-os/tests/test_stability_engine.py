import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from stability_engine import FrameTrend, SmartDecoder, diagnose_audio, detect_playback_profile, visual_state


class StabilityEngineTests(unittest.TestCase):
    def test_frame_trend_uses_counter_deltas_and_window(self):
        trend = FrameTrend(window=4)
        self.assertEqual(trend.update(10, 2, 0)["level"], "warming")
        trend.update(11, 3, 1)
        result = trend.update(30, 15, 2)
        self.assertEqual(result["vo_delta"], 19)
        self.assertEqual(result["decoder_delta"], 12)
        self.assertEqual(result["level"], "critical")

    def test_counter_reset_does_not_create_negative_delta(self):
        trend = FrameTrend()
        trend.update(20, 10, 0)
        result = trend.update(0, 0, 1)
        self.assertEqual(result["vo_delta"], 0)
        self.assertEqual(result["decoder_delta"], 0)

    def test_decoder_fallback_requires_evidence_and_is_limited(self):
        clock = lambda: 500
        decoder = SmartDecoder(clock)
        metrics = {"visual": {"state": "black_or_missing"},
                   "video": {"video_track": True},
                   "frame_trend": {"level": "critical", "decoder_window": 15}}
        decision = decoder.recommend(metrics, "default")
        self.assertEqual(decision["action"], "fallback")
        decoder.record_switch(decision["reason"])
        self.assertEqual(decoder.recommend(metrics, "compatible")["action"], "hold")
        self.assertEqual(decoder.recommend(metrics, "default")["action"], "hold")

    def test_audio_diagnostics_dont_claim_audible_sound(self):
        video = {"audio_track": True, "audio_pts": 10.0, "time_pos": 12.0}
        self.assertEqual(diagnose_audio(video)["state"], "track_active")
        self.assertIn("não comprova", diagnose_audio(video)["message"])
        self.assertEqual(diagnose_audio({"audio_track": False})["state"], "no_track")

    def test_visual_signal_is_proxy_not_hdmi_confirmation(self):
        video = {"video_track": True, "video_rendered": True}
        result = visual_state(video, True)
        self.assertEqual(result["state"], "progressing")
        self.assertEqual(result["confidence"], "medium")
        self.assertEqual(visual_state(video, False)["state"], "unknown")

    def test_pi3_profile_is_only_selected_on_explicit_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = Path(tmp) / "model"
            model.write_bytes(b"Raspberry Pi 3 Model B Rev 1.2\\x00")
            self.assertEqual(detect_playback_profile(model)["quality"], "economy")
            model.write_bytes(b"Generic ARM64 board\\x00")
            self.assertEqual(detect_playback_profile(model)["quality"], "balanced")


if __name__ == "__main__":
    unittest.main()
