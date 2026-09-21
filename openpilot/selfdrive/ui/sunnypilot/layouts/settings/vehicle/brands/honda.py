"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from openpilot.selfdrive.ui.sunnypilot.layouts.settings.vehicle.brands.base import BrandSettings
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.multilang import tr, tr_noop
from openpilot.system.ui.sunnypilot.widgets.list_view import toggle_item_sp

LOW_SPEED_PEDAL_DESC = tr_noop(
  "Removes the stock 0.4x throttle reduction below 10 m/s when sunnypilot drives through a comma pedal. " +
  "Only available when a comma pedal is detected. Test in an empty lot before road use. Takes effect on the next drive."
)


class HondaSettings(BrandSettings):
  def __init__(self):
    super().__init__()

    self.low_speed_pedal = toggle_item_sp(
      lambda: tr("Responsive Pedal at Low Speeds"),
      description=lambda: tr(LOW_SPEED_PEDAL_DESC),
      initial_state=ui_state.params.get_bool("HondaLowSpeedPedal"),
      callback=self._on_low_speed_pedal,
      enabled=lambda: ui_state.is_offroad(),
    )

    self.items = [
      self.low_speed_pedal,
    ]

  def _on_low_speed_pedal(self, state: bool):
    ui_state.params.put_bool("HondaLowSpeedPedal", state)
    ui_state.params.put_bool("OnroadCycleRequested", True)

  def update_settings(self):
    has_pedal = ui_state.CP_SP is not None and bool(ui_state.CP_SP.enableGasInterceptor)
    self.low_speed_pedal.set_visible(has_pedal)
