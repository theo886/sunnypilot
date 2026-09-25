"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""

from openpilot.cereal import custom
from opendbc.car.structs import car
from opendbc.car import structs
from openpilot.common.params import Params

ButtonType = car.CarState.ButtonEvent.Type
EventNameSP = custom.OnroadEventSP.EventName

DISTANCE_LONG_PRESS = 50
TRAFFIC_PARAM_REFRESH = 50  # frames at 100 Hz


class CruiseHelper:
  def __init__(self, CP: structs.CarParams):
    self.CP = CP
    self.params = Params()

    self.button_frame_counts = {ButtonType.gapAdjustCruise: 0}
    self._experimental_mode = False
    self.experimental_mode_switched = False

    # Traffic mode: opt-in, repurposes the distance-button hold. Not persisted; off at every start.
    self.traffic_mode_button = self.params.get_bool("TrafficModeButton")
    self.traffic_mode = False
    self._frame = 0

  def update(self, CS, events, experimental_mode, enabled: bool = True) -> None:
    self._frame += 1
    if self._frame % TRAFFIC_PARAM_REFRESH == 0:
      self.traffic_mode_button = self.params.get_bool("TrafficModeButton")
    if not self.traffic_mode_button or not enabled:
      self.traffic_mode = False

    if self.CP.openpilotLongitudinalControl:
      if CS.cruiseState.available:
        self.update_button_frame_counts(CS)

        if self.traffic_mode_button:
          # toggle traffic mode once on distance button hold, only while engaged
          self.update_traffic_mode(events, enabled)
        else:
          # toggle experimental mode once on distance button hold
          self.update_experimental_mode(events, experimental_mode)

  def update_button_frame_counts(self, CS) -> None:
    for button in self.button_frame_counts:
      if self.button_frame_counts[button] > 0:
        self.button_frame_counts[button] += 1

    for button_event in CS.buttonEvents:
      button = button_event.type.raw
      if button in self.button_frame_counts:
        self.button_frame_counts[button] = int(button_event.pressed)

  def update_experimental_mode(self, events, experimental_mode) -> None:
    if self.button_frame_counts[ButtonType.gapAdjustCruise] >= DISTANCE_LONG_PRESS and not self.experimental_mode_switched:
      self._experimental_mode = not experimental_mode
      self.params.put_bool("ExperimentalMode", self._experimental_mode)
      events.add(EventNameSP.experimentalModeSwitched)
      self.experimental_mode_switched = True

  def update_traffic_mode(self, events, enabled: bool) -> None:
    if self.button_frame_counts[ButtonType.gapAdjustCruise] >= DISTANCE_LONG_PRESS and not self.experimental_mode_switched:
      # the latch is shared with the experimental toggle: selfdrived uses it to skip the personality change on release
      self.experimental_mode_switched = True
      if enabled:
        self.traffic_mode = not self.traffic_mode
        events.add(EventNameSP.trafficModeOn if self.traffic_mode else EventNameSP.trafficModeOff)
