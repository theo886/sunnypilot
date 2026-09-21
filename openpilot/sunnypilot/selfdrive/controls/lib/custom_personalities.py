"""
User-adjustable follow time and jerk factor per driving personality.

Disabled by default. When disabled every getter returns None and the longitudinal
planner uses the built-in values from long_mpc. Values are clamped so a bad param
cannot ask the planner for an unsafe follow time or an unstable jerk weight.
"""
from openpilot.cereal import log
from openpilot.common.params import Params

Personality = log.LongitudinalPersonality

FOLLOW_KEYS: dict[int, str] = {
  int(Personality.aggressive): "AggressiveFollow",
  int(Personality.standard): "StandardFollow",
  int(Personality.relaxed): "RelaxedFollow",
}
JERK_KEYS: dict[int, str] = {
  int(Personality.aggressive): "AggressiveJerk",
  int(Personality.standard): "StandardJerk",
  int(Personality.relaxed): "RelaxedJerk",
}

T_FOLLOW_MIN, T_FOLLOW_MAX = 1.0, 3.0
JERK_MIN, JERK_MAX = 0.1, 2.0


def _clamp(value: float, lo: float, hi: float) -> float:
  return float(min(max(value, lo), hi))


def _key(personality) -> int:
  return int(getattr(personality, "raw", personality))


class CustomPersonalities:
  def __init__(self):
    self.params = Params()
    self.enabled = False
    self.t_follow: dict[int, float] = {}
    self.jerk: dict[int, float] = {}
    self._frame = 0
    self.read_params()

  def read_params(self) -> None:
    self.enabled = self.params.get_bool("CustomPersonalities")
    for p, key in FOLLOW_KEYS.items():
      self.t_follow[p] = _clamp(float(self.params.get(key, return_default=True)), T_FOLLOW_MIN, T_FOLLOW_MAX)
    for p, key in JERK_KEYS.items():
      self.jerk[p] = _clamp(float(self.params.get(key, return_default=True)), JERK_MIN, JERK_MAX)

  def update(self) -> None:
    self._frame += 1
    if self._frame % 50 == 0:  # 2.5 s at the planner's 20 Hz
      self.read_params()

  def get_t_follow(self, personality) -> float | None:
    return self.t_follow.get(_key(personality)) if self.enabled else None

  def get_jerk_factor(self, personality) -> float | None:
    return self.jerk.get(_key(personality)) if self.enabled else None
