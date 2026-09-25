from opendbc.car.structs import car
from openpilot.cereal import custom
from openpilot.common.params import Params
from openpilot.common.parameterized import parameterized_class
from openpilot.common.test import OpenpilotTestCase
from openpilot.selfdrive.selfdrived.events import Events
from openpilot.sunnypilot.selfdrive.car.cruise_helpers import CruiseHelper, DISTANCE_LONG_PRESS, TRAFFIC_PARAM_REFRESH
from openpilot.sunnypilot.selfdrive.selfdrived.events import EVENTS_SP

ButtonEvent = car.CarState.ButtonEvent
ButtonType = car.CarState.ButtonEvent.Type
EventNameSP = custom.OnroadEventSP.EventName


@parameterized_class(('openpilot_longitudinal',), [(True,)])
class TestCruiseHelper(OpenpilotTestCase):
  def setup_method(self):
    self.CP = car.CarParams(openpilotLongitudinalControl=self.openpilot_longitudinal)
    self.cruise_helper = CruiseHelper(self.CP)
    self.cruise_helper.experimental_mode_switched = False
    self.events = Events()

  def reset(self):
    for _ in range(2):
      CS = car.CarState(cruiseState={"available": False})
      CS.buttonEvents = [ButtonEvent(type=ButtonType.gapAdjustCruise, pressed=False)]
      self.cruise_helper._experimental_mode = False
      self.cruise_helper.experimental_mode_switched = False
      self.cruise_helper.update(CS, self.events, False)


  def test_gap_adjust_cruise_long_press_toggle_mode(self) -> None:
    for pressed in (True, False):
      for experimental_mode in (True, False):
        self.reset()
        self.cruise_helper._experimental_mode = experimental_mode
        toggled_mode = not experimental_mode if pressed else experimental_mode

        for i in range(DISTANCE_LONG_PRESS):
          CS = car.CarState(cruiseState={"available": True})
          CS.buttonEvents = [ButtonEvent(type=ButtonType.gapAdjustCruise, pressed=pressed)] if i == 0 else []
          self.cruise_helper.update(CS, self.events, experimental_mode)

        # mode should be toggled
        assert self.cruise_helper._experimental_mode == toggled_mode
        assert self.cruise_helper.experimental_mode_switched is pressed

        # keep holding button after switching mode
        for _ in range(DISTANCE_LONG_PRESS):
          CS = car.CarState(cruiseState={"available": True})
          CS.buttonEvents = [ButtonEvent(type=ButtonType.gapAdjustCruise, pressed=pressed)]
          self.cruise_helper.update(CS, self.events, toggled_mode)

        # mode should not be toggled
        assert self.cruise_helper._experimental_mode == toggled_mode
        assert self.cruise_helper.experimental_mode_switched is pressed

  def test_gap_adjust_cruise_short_press_toggle_mode(self) -> None:
    for pressed in (True, False):
      for experimental_mode in (True, False):
        self.reset()
        self.cruise_helper._experimental_mode = experimental_mode

        for i in range(DISTANCE_LONG_PRESS - 1):
          CS = car.CarState(cruiseState={"available": True})
          CS.buttonEvents = [ButtonEvent(type=ButtonType.gapAdjustCruise, pressed=pressed)] if i == 0 else []
          self.cruise_helper.update(CS, self.events, experimental_mode)

        # mode should not be toggled
        assert self.cruise_helper._experimental_mode == experimental_mode
        assert self.cruise_helper.experimental_mode_switched is False

  def _hold(self, frames, enabled=True, experimental_mode=False):
    for i in range(frames):
      CS = car.CarState(cruiseState={"available": True})
      CS.buttonEvents = [ButtonEvent(type=ButtonType.gapAdjustCruise, pressed=True)] if i == 0 else []
      self.cruise_helper.update(CS, self.events, experimental_mode, enabled=enabled)

  def _release(self, enabled=True):
    CS = car.CarState(cruiseState={"available": True})
    CS.buttonEvents = [ButtonEvent(type=ButtonType.gapAdjustCruise, pressed=False)]
    self.cruise_helper.update(CS, self.events, False, enabled=enabled)

  def _with_traffic_param(self, value):
    Params().put_bool("TrafficModeButton", value, block=True)
    self.cruise_helper = CruiseHelper(self.CP)
    self.events = Events()

  def teardown_method(self):
    Params().remove("TrafficModeButton")

  def test_traffic_param_off_keeps_experimental_toggle(self):
    self._with_traffic_param(False)
    self._hold(DISTANCE_LONG_PRESS)
    assert self.cruise_helper._experimental_mode is True
    assert self.cruise_helper.traffic_mode is False

  def test_traffic_hold_toggles_traffic_not_experimental(self):
    self._with_traffic_param(True)
    self._hold(DISTANCE_LONG_PRESS)
    assert self.cruise_helper.traffic_mode is True
    assert self.cruise_helper._experimental_mode is False
    assert self.cruise_helper.experimental_mode_switched is True  # review focus 3: suppresses personality cycle
    assert EventNameSP.trafficModeOn in self.events.names

  def test_traffic_hold_once_per_press(self):
    self._with_traffic_param(True)
    self._hold(DISTANCE_LONG_PRESS * 3)  # keep holding: exactly one toggle
    assert self.cruise_helper.traffic_mode is True
    assert self.events.names == [EventNameSP.trafficModeOn]
    self._release()
    self.cruise_helper.experimental_mode_switched = False  # selfdrived clears the latch on release
    self.events = Events()
    self._hold(DISTANCE_LONG_PRESS)
    assert self.cruise_helper.traffic_mode is False
    assert self.events.names == [EventNameSP.trafficModeOff]

  def test_traffic_hold_ignored_when_not_engaged(self):
    # Review focus 1
    self._with_traffic_param(True)
    self._hold(DISTANCE_LONG_PRESS, enabled=False)
    assert self.cruise_helper.traffic_mode is False
    assert self.cruise_helper._experimental_mode is False
    assert EventNameSP.trafficModeOn not in self.events.names

  def test_traffic_clears_on_disengage(self):
    # Review focus 2
    self._with_traffic_param(True)
    self._hold(DISTANCE_LONG_PRESS)
    assert self.cruise_helper.traffic_mode is True
    self.events = Events()
    CS = car.CarState(cruiseState={"available": True})
    self.cruise_helper.update(CS, self.events, False, enabled=False)
    assert self.cruise_helper.traffic_mode is False
    assert EventNameSP.trafficModeOff not in self.events.names  # silent: the disengage alert already sounds

  def test_traffic_clears_when_param_turned_off(self):
    # Review focus 4
    self._with_traffic_param(True)
    self._hold(DISTANCE_LONG_PRESS)
    assert self.cruise_helper.traffic_mode is True
    Params().put_bool("TrafficModeButton", False, block=True)
    for _ in range(TRAFFIC_PARAM_REFRESH):
      self.cruise_helper.update(car.CarState(cruiseState={"available": True}), self.events, False, enabled=True)
    assert self.cruise_helper.traffic_mode is False

  def test_traffic_alerts_registered(self):
    assert EventNameSP.trafficModeOn in EVENTS_SP
    assert EventNameSP.trafficModeOff in EVENTS_SP
