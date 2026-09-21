from openpilot.cereal import log

from openpilot.common.params import Params
from openpilot.common.test import OpenpilotTestCase
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
