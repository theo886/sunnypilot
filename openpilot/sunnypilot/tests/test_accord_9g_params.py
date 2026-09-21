from openpilot.common.params import Params
from openpilot.common.test import OpenpilotTestCase
from openpilot.sunnypilot.selfdrive.car.interfaces import initialize_params

INT_DEFAULTS = {
  "EngageVolume": 101, "DisengageVolume": 101, "PromptVolume": 101, "PromptDistractedVolume": 101,
  "RefuseVolume": 101, "WarningSoftVolume": 101, "WarningImmediateVolume": 101,
}
FLOAT_DEFAULTS = {
  "AggressiveFollow": 1.25, "StandardFollow": 1.45, "RelaxedFollow": 1.75,
  "AggressiveJerk": 0.5, "StandardJerk": 1.0, "RelaxedJerk": 1.0,
}


class TestAccord9GParams(OpenpilotTestCase):
  def test_int_defaults(self):
    p = Params()
    for key, default in INT_DEFAULTS.items():
      assert p.get(key, return_default=True) == default, key

  def test_float_defaults(self):
    p = Params()
    for key, default in FLOAT_DEFAULTS.items():
      assert abs(p.get(key, return_default=True) - default) < 1e-9, key

  def test_bool_defaults(self):
    p = Params()
    assert p.get_bool("HondaLowSpeedPedal") is False
    assert p.get_bool("CustomPersonalities") is False

  def test_honda_low_speed_pedal_reaches_opendbc(self):
    p = Params()
    p.put_bool("HondaLowSpeedPedal", True, block=True)
    try:
      merged = {k: v for d in initialize_params(p) for k, v in d.items()}
      assert merged["HondaLowSpeedPedal"] is True
    finally:
      p.remove("HondaLowSpeedPedal")
