"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from unittest import mock

import pytest

from openpilot.cereal import log
import openpilot.cereal.messaging as messaging
from openpilot.common.params import Params
from openpilot.common.test import OpenpilotTestCase
from openpilot.selfdrive.controls.lib.longitudinal_mpc_lib.long_mpc import (
  A_CHANGE_COST, J_EGO_COST, LongitudinalMpc, get_T_FOLLOW, get_jerk_factor,
)
from openpilot.selfdrive.controls.tests.test_following_distance import desired_follow_distance, run_following_distance_simulation
from openpilot.sunnypilot.selfdrive.controls.lib.custom_personalities import (
  CustomPersonalities, FOLLOW_KEYS, JERK_KEYS, T_FOLLOW_MIN, T_FOLLOW_MAX, JERK_MIN, JERK_MAX,
  TRAFFIC_JERK, TRAFFIC_T_FOLLOW_BP, TRAFFIC_T_FOLLOW_V,
)

Personality = log.LongitudinalPersonality
ALL_KEYS = ["CustomPersonalities", *FOLLOW_KEYS.values(), *JERK_KEYS.values()]


def minimal_radarstate():
  return messaging.new_message('radarState').radarState


class TestCustomPersonalities(OpenpilotTestCase):
  def setup_method(self):
    self.params = Params()
    for key in ALL_KEYS:
      self.params.remove(key)

  def teardown_method(self):
    for key in ALL_KEYS:
      self.params.remove(key)

  def test_disabled_returns_none(self):
    cp = CustomPersonalities()
    for p in (Personality.aggressive, Personality.standard, Personality.relaxed):
      assert cp.get_t_follow(p) is None
      assert cp.get_jerk_factor(p) is None

  def test_enabled_defaults_match_stock(self):
    self.params.put_bool("CustomPersonalities", True, block=True)
    cp = CustomPersonalities()
    for p in (Personality.aggressive, Personality.standard, Personality.relaxed):
      assert abs(cp.get_t_follow(p) - get_T_FOLLOW(p)) < 1e-9
      assert abs(cp.get_jerk_factor(p) - get_jerk_factor(p)) < 1e-9

  def test_enabled_reads_params(self):
    self.params.put_bool("CustomPersonalities", True, block=True)
    self.params.put("StandardFollow", 2.2, block=True)
    self.params.put("StandardJerk", 0.7, block=True)
    cp = CustomPersonalities()
    assert abs(cp.get_t_follow(Personality.standard) - 2.2) < 1e-9
    assert abs(cp.get_jerk_factor(Personality.standard) - 0.7) < 1e-9
    assert abs(cp.get_t_follow(Personality.relaxed) - 1.75) < 1e-9

  def test_clamps(self):
    self.params.put_bool("CustomPersonalities", True, block=True)
    self.params.put("AggressiveFollow", 0.2, block=True)
    self.params.put("RelaxedFollow", 9.0, block=True)
    self.params.put("AggressiveJerk", 0.0, block=True)
    self.params.put("RelaxedJerk", 5.0, block=True)
    cp = CustomPersonalities()
    assert cp.get_t_follow(Personality.aggressive) == T_FOLLOW_MIN
    assert cp.get_t_follow(Personality.relaxed) == T_FOLLOW_MAX
    assert cp.get_jerk_factor(Personality.aggressive) == JERK_MIN
    assert cp.get_jerk_factor(Personality.relaxed) == JERK_MAX

  def test_update_refreshes_every_fifty_frames(self):
    cp = CustomPersonalities()
    self.params.put_bool("CustomPersonalities", True, block=True)
    for _ in range(49):
      cp.update()
    assert cp.get_t_follow(Personality.standard) is None
    cp.update()
    assert cp.get_t_follow(Personality.standard) is not None

  def test_accepts_raw_enum_values(self):
    self.params.put_bool("CustomPersonalities", True, block=True)
    cp = CustomPersonalities()
    assert cp.get_t_follow(int(Personality.aggressive)) == cp.get_t_follow(Personality.aggressive)

  def test_traffic_mode_follow_time_interpolates(self):
    cp = CustomPersonalities()
    assert abs(cp.get_t_follow(Personality.standard, v_ego=0.0, traffic_mode=True) - 0.5) < 1e-9
    assert abs(cp.get_t_follow(Personality.standard, v_ego=2.5, traffic_mode=True) - 0.75) < 1e-9
    assert abs(cp.get_t_follow(Personality.standard, v_ego=5.0, traffic_mode=True) - 1.0) < 1e-9
    assert abs(cp.get_t_follow(Personality.standard, v_ego=30.0, traffic_mode=True) - 1.0) < 1e-9
    assert (TRAFFIC_T_FOLLOW_BP, TRAFFIC_T_FOLLOW_V, TRAFFIC_JERK) == ([0.0, 5.0], [0.5, 1.0], 0.5)

  def test_traffic_mode_jerk(self):
    cp = CustomPersonalities()
    assert cp.get_jerk_factor(Personality.relaxed, traffic_mode=True) == TRAFFIC_JERK

  def test_traffic_mode_applies_without_custom_personalities(self):
    # Review focus 5: traffic values do not depend on the CustomPersonalities toggle
    assert not self.params.get_bool("CustomPersonalities")
    cp = CustomPersonalities()
    assert cp.get_t_follow(Personality.aggressive, v_ego=0.0, traffic_mode=True) == 0.5
    assert cp.get_jerk_factor(Personality.aggressive, traffic_mode=True) == TRAFFIC_JERK

  def test_traffic_mode_overrides_custom_values(self):
    self.params.put_bool("CustomPersonalities", True, block=True)
    self.params.put("StandardFollow", 2.5, block=True)
    cp = CustomPersonalities()
    assert cp.get_t_follow(Personality.standard, v_ego=0.0, traffic_mode=True) == 0.5
    assert cp.get_t_follow(Personality.standard, v_ego=0.0, traffic_mode=False) == 2.5

  def test_traffic_floor_is_separate_from_custom_floor(self):
    assert T_FOLLOW_MIN == 1.0


class TestCustomPersonalitiesInMpc(OpenpilotTestCase):
  """The overrides must reach the MPC's own state. These do not need the solver to converge."""

  def _t_follow_stored(self, **kwargs):
    mpc = LongitudinalMpc()
    # run() calls reset() on a failed solve, which zeroes self.params; neutralise it so we can
    # read back exactly what update() stored (long_mpc.py:334 `self.params[:,4] = t_follow`).
    with mock.patch.object(mpc, "run"):
      mpc.update(minimal_radarstate(), **kwargs)
    return mpc.params[:, 4]

  def _cost_weights(self, **kwargs):
    mpc = LongitudinalMpc()
    # The acados solver exposes no cost_get(), so capture the list built at long_mpc.py:267.
    with mock.patch.object(mpc, "set_cost_weights", wraps=mpc.set_cost_weights) as spy:
      mpc.set_weights(True, **kwargs)
    return spy.call_args[0][0]

  def test_t_follow_override_lands_in_params(self):
    stored = self._t_follow_stored(personality=Personality.standard, t_follow=2.5)
    assert (stored == 2.5).all(), stored

  def test_t_follow_none_uses_builtin(self):
    stored = self._t_follow_stored(personality=Personality.standard, t_follow=None)
    assert (stored == get_T_FOLLOW(Personality.standard)).all(), stored

  def test_jerk_factor_override_lands_in_cost_weights(self):
    weights = self._cost_weights(personality=Personality.standard, jerk_factor=0.7)
    assert abs(weights[4] - 0.7 * A_CHANGE_COST) < 1e-9
    assert abs(weights[5] - 0.7 * J_EGO_COST) < 1e-9

  def test_jerk_factor_none_uses_builtin(self):
    builtin = get_jerk_factor(Personality.standard)
    weights = self._cost_weights(personality=Personality.standard, jerk_factor=None)
    assert abs(weights[4] - builtin * A_CHANGE_COST) < 1e-9
    assert abs(weights[5] - builtin * J_EGO_COST) < 1e-9


class TestCustomPersonalitiesInPlanner(OpenpilotTestCase):
  def setup_method(self):
    self.params = Params()
    for key in ALL_KEYS:
      self.params.remove(key)

  def teardown_method(self):
    for key in ALL_KEYS:
      self.params.remove(key)

  def _planner_kwargs(self):
    """Run one planner frame with the MPC stubbed out and return the kwargs it was handed."""
    from openpilot.selfdrive.test.longitudinal_maneuvers.plant import Plant

    plant = Plant(lead_relevancy=True, speed=20.0, distance_lead=50.0, personality=Personality.standard)
    with mock.patch.object(plant.planner.mpc, "set_weights") as set_weights, \
         mock.patch.object(plant.planner.mpc, "update") as update:
      plant.step(v_lead=20.0)
    return set_weights.call_args.kwargs, update.call_args.kwargs

  def test_planner_passes_overrides_when_enabled(self):
    self.params.put_bool("CustomPersonalities", True, block=True)
    self.params.put("StandardFollow", 2.5, block=True)
    self.params.put("StandardJerk", 0.7, block=True)
    weights_kwargs, update_kwargs = self._planner_kwargs()
    assert weights_kwargs["personality"] == Personality.standard
    assert abs(weights_kwargs["jerk_factor"] - 0.7) < 1e-9
    assert abs(update_kwargs["t_follow"] - 2.5) < 1e-9

  def test_planner_passes_none_when_disabled(self):
    weights_kwargs, update_kwargs = self._planner_kwargs()
    assert weights_kwargs["jerk_factor"] is None
    assert update_kwargs["t_follow"] is None

  def test_custom_follow_time_changes_steady_state_distance(self):
    v_lead = 20.0
    # This needs the acados long MPC to actually converge, which it does not on every host
    # (macOS: "SQP_RTI: QP solver returned error status 3"). Prove the stock case first.
    stock = desired_follow_distance(v_lead, v_lead, get_T_FOLLOW(Personality.standard))
    stock_sim = run_following_distance_simulation(v_lead, e2e=False, personality=Personality.standard)
    if abs(stock_sim - stock) > 0.2 * stock:
      pytest.skip("acados MPC does not converge on this host")

    self.params.put_bool("CustomPersonalities", True, block=True)
    self.params.put("StandardFollow", 2.5, block=True)
    steady = run_following_distance_simulation(v_lead, e2e=False, personality=Personality.standard)
    expected = desired_follow_distance(v_lead, v_lead, 2.5)
    assert abs(steady - expected) < 0.1 * expected + 0.5, (steady, expected)
    assert steady > stock + 5.0, "custom follow time did not reach the planner"

  def _planner_kwargs_traffic(self, speed):
    from openpilot.selfdrive.test.longitudinal_maneuvers.plant import Plant

    plant = Plant(lead_relevancy=True, speed=speed, distance_lead=50.0, personality=Personality.standard)
    orig_update = plant.planner.update

    def update_with_traffic(sm):
      sm['selfdriveStateSP'].trafficMode = True
      return orig_update(sm)

    with mock.patch.object(plant.planner, "update", side_effect=update_with_traffic), \
         mock.patch.object(plant.planner.mpc, "set_weights") as set_weights, \
         mock.patch.object(plant.planner.mpc, "update") as update:
      plant.step(v_lead=speed)
    return set_weights.call_args.kwargs, update.call_args.kwargs, plant.planner.v_desired_filter.x

  def test_planner_passes_traffic_values(self):
    weights_kwargs, update_kwargs, _ = self._planner_kwargs_traffic(speed=0.0)
    assert weights_kwargs["jerk_factor"] == 0.5
    assert abs(update_kwargs["t_follow"] - 0.5) < 0.05  # v_desired_filter may be a hair above 0

  def test_planner_passes_traffic_values_at_speed(self):
    # Plant builds the planner with init_v=speed, so v_desired_filter starts at 10 m/s and a 10 m/s v_ego keeps it
    # there. The planner must hand get_t_follow that speed: without v_ego it would interpolate at 0 and return 0.5.
    weights_kwargs, update_kwargs, v_filter = self._planner_kwargs_traffic(speed=10.0)
    assert abs(v_filter - 10.0) < 0.1
    assert weights_kwargs["jerk_factor"] == 0.5
    assert abs(update_kwargs["t_follow"] - 1.0) < 1e-6

  def test_planner_traffic_off_unchanged(self):
    weights_kwargs, update_kwargs = self._planner_kwargs()
    assert weights_kwargs["jerk_factor"] is None
    assert update_kwargs["t_follow"] is None
