import numpy as np

from openpilot.cereal import log

from openpilot.common.params import Params
from openpilot.common.test import OpenpilotTestCase
from openpilot.selfdrive.ui.soundd import Soundd
from openpilot.sunnypilot.selfdrive.ui.alert_volume import AlertVolume, VOLUME_PARAMS, AUTO, WARNING_FLOOR

# alert_volume.py keys VOLUME_PARAMS off opendbc's car.CarControl.HUDControl.AudibleAlert (matching
# quiet_mode.py), which lacks preAlert/complete. cereal's log.SelfdriveState.AudibleAlert is the superset
# soundd.py actually assigns to self.current_alert, and its shared member values (engage, disengage, ...)
# are numerically identical to opendbc's, so it's the right enum for this test to exercise scale() with.
AudibleAlert = log.SelfdriveState.AudibleAlert


class TestAlertVolume(OpenpilotTestCase):
  def setup_method(self):
    self.params = Params()
    for key in set(VOLUME_PARAMS.values()):
      self.params.remove(key)

  def teardown_method(self):
    for key in set(VOLUME_PARAMS.values()):
      self.params.remove(key)

  def test_defaults_are_automatic(self):
    av = AlertVolume()
    for alert in VOLUME_PARAMS:
      assert av.scale(alert) == 1.0

  def test_unmapped_alert_is_automatic(self):
    av = AlertVolume()
    assert av.scale(AudibleAlert.preAlert) == 1.0
    assert av.scale(AudibleAlert.none) == 1.0

  def test_percent_scales_linearly(self):
    self.params.put("EngageVolume", 50, block=True)
    av = AlertVolume()
    assert abs(av.scale(AudibleAlert.engage) - 0.5) < 1e-9
    assert av.scale(AudibleAlert.disengage) == 1.0

  def test_zero_mutes_non_warning(self):
    self.params.put("DisengageVolume", 0, block=True)
    self.params.put("PromptDistractedVolume", 0, block=True)
    av = AlertVolume()
    assert av.scale(AudibleAlert.disengage) == 0.0
    assert av.scale(AudibleAlert.promptDistracted) == 0.0

  def test_prompt_and_prompt_repeat_share_a_key(self):
    self.params.put("PromptVolume", 20, block=True)
    av = AlertVolume()
    assert abs(av.scale(AudibleAlert.prompt) - 0.2) < 1e-9
    assert abs(av.scale(AudibleAlert.promptRepeat) - 0.2) < 1e-9

  def test_warnings_have_a_floor(self):
    self.params.put("WarningSoftVolume", 0, block=True)
    self.params.put("WarningImmediateVolume", 10, block=True)
    av = AlertVolume()
    assert abs(av.scale(AudibleAlert.warningSoft) - WARNING_FLOOR / 100) < 1e-9
    assert abs(av.scale(AudibleAlert.warningImmediate) - WARNING_FLOOR / 100) < 1e-9

  def test_values_above_auto_are_automatic(self):
    self.params.put("RefuseVolume", 250, block=True)
    av = AlertVolume()
    assert av.scale(AudibleAlert.refuse) == 1.0
    assert AUTO == 101

  def test_load_param_refreshes_every_fifty_calls(self):
    av = AlertVolume()
    self.params.put("EngageVolume", 30, block=True)
    for _ in range(49):
      av.load_param()
    assert av.scale(AudibleAlert.engage) == 1.0
    av.load_param()
    assert abs(av.scale(AudibleAlert.engage) - 0.3) < 1e-9

  def test_pending_stop_buffer_is_still_scaled(self):
    # Regression test: get_sound_data's pending_stop branch used to set self.current_alert to
    # AudibleAlert.none *inside* the fill loop, so the old `ret * self.current_volume *
    # self.alert_volume.scale(self.current_alert)` evaluated the scale AFTER the mutation and
    # returned 1.0 for the last (still audible) buffer of every looping alert. The scale must be
    # snapshotted before the loop can touch current_alert, so every buffer -- including the one
    # where the sound actually stops mid-fill -- is scaled consistently.
    s_auto = Soundd()  # WarningSoftVolume unset -> automatic / unscaled reference
    s_auto.current_volume = 1.0
    s_auto.update_alert(AudibleAlert.warningSoft)

    self.params.put("WarningSoftVolume", 0, block=True)
    s_scaled = Soundd()
    s_scaled.current_volume = 1.0
    s_scaled.update_alert(AudibleAlert.warningSoft)

    # Play enough buffers to get past one full loop of critical.wav (25714 frames / 4096 per
    # buffer) so the alert has "played once" and a stop request becomes a pending_stop instead of
    # an immediate cut.
    for _ in range(8):
      s_auto.get_sound_data(4096)
      s_scaled.get_sound_data(4096)

    s_auto.update_alert(AudibleAlert.none)
    s_scaled.update_alert(AudibleAlert.none)
    assert s_auto.pending_stop and s_scaled.pending_stop

    # Pull buffers until the sound actually stops, checking every one along the way -- including
    # the final buffer, where current_alert flips to `none` partway through the fill loop.
    stopped = False
    for _ in range(15):
      auto_buf = s_auto.get_sound_data(4096)
      scaled_buf = s_scaled.get_sound_data(4096)
      assert abs(scaled_buf).max() <= WARNING_FLOOR / 100 * abs(auto_buf).max() + 1e-6
      if s_auto.current_alert == AudibleAlert.none and s_scaled.current_alert == AudibleAlert.none:
        stopped = True
        break
    assert stopped, "warningSoft sound never stopped"

  def test_pending_stop_buffer_is_muted_when_zero(self):
    # Companion to the floor regression above: promptDistracted has no floor, so a 0 %
    # volume must mute it completely, including the final buffer where the sound stops.
    self.params.put("PromptDistractedVolume", 0, block=True)
    s = Soundd()
    s.current_volume = 1.0
    s.update_alert(AudibleAlert.promptDistracted)

    # Play past one full loop of dm_warning.wav (36000 frames / 4096 per buffer).
    for _ in range(10):
      assert np.all(s.get_sound_data(4096) == 0.0)

    s.update_alert(AudibleAlert.none)
    assert s.pending_stop

    final_buf = None
    stopped = False
    for _ in range(15):
      final_buf = s.get_sound_data(4096)
      assert np.all(final_buf == 0.0)
      if s.current_alert == AudibleAlert.none:
        stopped = True
        break
    assert stopped, "promptDistracted sound never stopped"
    assert np.all(final_buf == 0.0)
