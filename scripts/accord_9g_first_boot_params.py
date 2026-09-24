#!/usr/bin/env python3
"""
One-time settings for Theo's 2017 Accord Hybrid on the comma four.
Run on the device over SSH after the first boot of the accord-hybrid-9g branch, before the first drive:

  ssh comma@<ip> 'cd /data/openpilot && PYTHONPATH=/data/openpilot /usr/local/venv/bin/python3 scripts/accord_9g_first_boot_params.py'

A one-shot `ssh comma@<ip> '...'` is not a login shell, so plain python3 is /usr/bin/python3 without
openpilot's venv, and /data/openpilot is not on the import path. Inside an interactive SSH session plain
`python3 scripts/accord_9g_first_boot_params.py` works. See docs/ACCORD_HYBRID_9G.md, Install step 4.

Every value here reproduces the comma 3X's behaviour or keeps a new feature off until it has been tested.

Every write blocks until it is persisted, so the values printed at the end are the values that are
really stored. Without block=True a write is not visible to a read in the same process, and on a
fresh params store the summary would print the stock defaults instead of what was just set.
"""
from openpilot.common.params import Params


def main() -> None:
  p = Params()
  p.put("LongitudinalPersonality", 0, block=True)          # aggressive, as on the 3X (follow 1.25 s)
  p.put_bool("DisengageOnAccelerator", False, block=True)  # as on the 3X
  p.put_bool("Mads", False, block=True)                    # off until an engaged-drive log exists (spec section 10)
  p.put_bool("HondaLowSpeedPedal", False, block=True)      # turn on only after the empty-lot test
  p.put_bool("CustomPersonalities", False, block=True)     # defaults equal stock; enable when wanted
  p.put_bool("QuietMode", False, block=True)
  volume_keys = ("EngageVolume", "DisengageVolume", "PromptVolume", "PromptDistractedVolume",
                 "RefuseVolume", "WarningSoftVolume", "WarningImmediateVolume")
  for key in volume_keys:
    p.put(key, 101, block=True)                            # automatic
  print("accord 9g params set:")
  for key in ("LongitudinalPersonality", "DisengageOnAccelerator", "Mads", "HondaLowSpeedPedal",
              "CustomPersonalities", "QuietMode") + volume_keys:
    print(f"  {key} = {p.get(key, return_default=True)!r}")


if __name__ == "__main__":
  main()
