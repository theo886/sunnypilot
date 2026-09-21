# 2017 Accord Hybrid on the comma four (accord-hybrid-9g)

Branch: `theo886/sunnypilot` `accord-hybrid-9g`, opendbc `theo886/opendbc` `accord-hybrid-9g`.
Base: sunnypilot master-dev a5f4465 (openpilot 0.11.2, AGNOS 19.7). Panda: sunnypilot's stock panda, unchanged.

## What this branch adds

- Platform `HONDA_ACCORD_HYBRID_9G`: serial steering board on bus 0 (0xE4 out, 0x190 in, torque cap 239), comma pedal (0x200/0x201), hybrid brake field, gear from 0x188.
- `HondaLowSpeedPedal` (off): removes the 0.4x throttle reduction below 10 m/s. Empty-lot test first.
- `EngageVolume` ... `WarningImmediateVolume` (101 = automatic): per-category chime volume, warnings never below 25%.
- `CustomPersonalities` (off) with `AggressiveFollow/StandardFollow/RelaxedFollow` (s) and `AggressiveJerk/StandardJerk/RelaxedJerk`.

## Known facts from the log replay (part 1)

These came out of replaying the 3X logs and out of the reviews. Read them before the bench test so that normal behaviour is not mistaken for a failure.

- **The board boots about 5 s after the panda** (4.92 s observed). Until then `STEER_STATUS` 0x190 is absent, so openpilot shows CAN-invalid / not ready for roughly 5 s at every ignition. There is deliberately no grace logic in `CarState`: a board that never boots must stay visible as a fault. This 5 s window is normal and is not a bench failure.
- **A burst of rejected TX frames at ignition is normal.** Ignition-start logs contain about 14 rejected-TX frames (src 192) inside a 50 ms window roughly 0.5 s after the board boots. Mid-drive logs have zero. Rejections after that window mean the panda is refusing commands: stop and investigate.
- **The gateway firmware `38897-T3W-0130` is not in the logged `carFw`** (only fwdRadar `36161-T3Z-A830` and srs `77959-T3Z-A020` were logged), and fingerprinting still matched exactly without it. First bench step: confirm the live FW query on the comma four still fingerprints `HONDA_ACCORD_HYBRID_9G` before anything else.
- **Board telemetry** `SS_STATUS` 0x208 decodes `VERSION_NUM` 2 / `HARDWARE_REV` 4. `LATE_CAN_MSG` is set in a handful of frames at ignition and never after boot.
- **`maxLateralAccel` 0.35 is a placeholder** carried over from the torque-data override. It is informational only for this PID-lateral car until torqued converges on real values.
- **`STEER_THRESHOLD` 30 is crossed 47 % of driving time** in the 3X logs, so `steeringPressed` will be noisy. Re-derive it together with the steer ratio (13.66 static vs 18.42 learned) after an engaged drive.
- **Panda safety on the car:** `hondaNidec`, param 4 (`NIDEC_ALT`), sunnypilot param 3 (`NIDEC_HYBRID | GAS_INTERCEPTOR`). Do NOT carry over the 3X's param 20.
- **The inherited replay test `test_panda_safety_tx_cases` is skipped for every Honda hybrid** because of a test-harness flag collision (`ToyotaFlags.SECOC` == `HondaFlags.HYBRID` == 2048). TX limits are covered instead by the dedicated `TestHondaNidecAltHybridGasInterceptorSafety` class.
- **Volume params:** 0..100 is a percentage, 101 is automatic. The two warning categories never go below 25 % (the device panel shows 25 % for any lower stored value). sunnypilot's `promptSingleLow` / `promptSingleHigh` sounds are not mapped to any volume param and always play at automatic volume.
- **`HondaLowSpeedPedal` only has an effect when the comma pedal is fingerprinted** (0x201 on bus 0). The matching sunnylink item is hidden unless the `gas_interceptor` capability is true.

## Install (first time)

1. On the comma four, at setup choose Custom Software and enter the install URL for sunnypilot's `master-dev` branch from the Installation page at https://community.sunnypilot.ai/docs (do not guess the URL). This flashes AGNOS 19.7 and, on first car connection, the comma four's built-in panda with sunnypilot's stock panda firmware. The 3X and its panda are untouched.
2. Enable SSH in Settings and add GitHub user `theo886`.
3. From the Mac:

    ssh comma@<comma-four-ip>
    cd /data/openpilot
    git remote set-url origin https://github.com/theo886/sunnypilot.git
    git fetch origin accord-hybrid-9g
    git checkout accord-hybrid-9g
    git submodule sync && git submodule update --init --recursive
    sudo reboot

4. The first boot compiles the branch on the device (10 to 20 minutes, screen shows the build). Then:

    ssh comma@<comma-four-ip> 'cd /data/openpilot && python3 scripts/accord_9g_first_boot_params.py'

## Setting params without a panel (comma four)

The comma four UI has no Vehicle or Cruise panel. Use sunnylink (Settings, sunnylink, pair) or SSH:

    cd /data/openpilot && python3 -c "from openpilot.common.params import Params; Params().put_bool('HondaLowSpeedPedal', True)"

Bool keys: HondaLowSpeedPedal, CustomPersonalities, QuietMode, Mads, DisengageOnAccelerator.
Int keys: LongitudinalPersonality (0 aggressive, 1 standard, 2 relaxed), the seven *Volume keys (0..101).
Float keys: AggressiveFollow, StandardFollow, RelaxedFollow (1.0..3.0), AggressiveJerk, StandardJerk, RelaxedJerk (0.1..2.0).

## Tests that cannot run on the Mac

Two checks do not pass on macOS arm64 and must be run on a Linux box or on the device before the results are trusted:

- `openpilot/selfdrive/controls/tests/test_following_distance.py` fails on the Mac: the acados MPC does not converge on macOS arm64.
- The custom-personalities steady-state simulation test skips for the same reason. Run `openpilot/sunnypilot/selfdrive/controls/lib/tests/test_custom_personalities.py` on Linux or on the device before trusting the follow-time override on the road.

## Rollback

- Before the road test passes: unplug the comma four, plug the 3X back in. Nothing on the 3X changed.
- On the comma four: `cd /data/openpilot && git checkout <known-good tag or sha> && sudo reboot`. The tag for each drive is written in the handoff note.

## Test ladder (spec section 8)

1. Replay on the Mac: done in part 1 (`ACCORD_9G_RLOG=... pytest opendbc/car/honda/tests/test_accord_hybrid_9g_replay.py`).
2. Bench, car parked, ignition on, nothing engaged: automatic fingerprint to HONDA_ACCORD_HYBRID_9G, no steer fault after the board boots, pedal detected, `pandaStates` safety model hondaNidec with param 4 and sunnypilot param 3. Check with `ssh comma@<ip> 'cat /data/params/d/CarParamsPersistent | strings | head'` and the on-screen alerts.
3. Empty lot, driver only: lateral at walking speed, then longitudinal, stop and pedal start with `HondaLowSpeedPedal` off then on. Trigger engage and disengage chimes for the volume feature. Save the routes.
4. Road, normal use. Re-derive steer ratio and steering-pressed threshold from these logs (spec section 9).

Anything that touches the board (steering) or the pedal (longitudinal) is stationary-first, then lot, then road. No exceptions.
