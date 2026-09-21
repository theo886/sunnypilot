"""
Per-category alert volume scaling for soundd.

Each alert category has a param holding 0..100 (percent) or 101 (automatic, the stock
ambient-noise-based volume). The two warning categories never drop below WARNING_FLOOR
so safety warnings cannot be muted. Quiet Mode decides whether a sound plays at all;
this class only scales sounds that play.
"""
from opendbc.car.structs import car

from openpilot.common.params import Params

AudibleAlert = car.CarControl.HUDControl.AudibleAlert

AUTO = 101
WARNING_FLOOR = 25

VOLUME_PARAMS: dict[int, str] = {
  AudibleAlert.engage: "EngageVolume",
  AudibleAlert.disengage: "DisengageVolume",
  AudibleAlert.refuse: "RefuseVolume",
  AudibleAlert.prompt: "PromptVolume",
  AudibleAlert.promptRepeat: "PromptVolume",
  AudibleAlert.promptDistracted: "PromptDistractedVolume",
  AudibleAlert.warningSoft: "WarningSoftVolume",
  AudibleAlert.warningImmediate: "WarningImmediateVolume",
}

FLOORED_ALERTS = {AudibleAlert.warningSoft, AudibleAlert.warningImmediate}


class AlertVolume:
  def __init__(self):
    self.params = Params()
    self._frame = 0
    self.levels: dict[int, int] = {}
    self.read_params()

  def read_params(self) -> None:
    for alert, key in VOLUME_PARAMS.items():
      self.levels[alert] = int(self.params.get(key, return_default=True))

  def load_param(self) -> None:
    self._frame += 1
    if self._frame % 50 == 0:  # 2.5 seconds at soundd's 20 Hz
      self.read_params()

  def scale(self, current_alert: int) -> float:
    level = self.levels.get(current_alert, AUTO)
    if level >= AUTO:
      return 1.0
    if current_alert in FLOORED_ALERTS:
      level = max(level, WARNING_FLOOR)
    return max(0, min(level, 100)) / 100.0
