#!/usr/bin/env python3
"""
One-time settings for Theo's 2017 Accord Hybrid on the comma four.
Run on the device over SSH after the first boot of the accord-hybrid-9g branch, before the first drive:

  cd /data/openpilot && python3 scripts/accord_9g_first_boot_params.py

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
  for key in ("EngageVolume", "DisengageVolume", "PromptVolume", "PromptDistractedVolume",
              "RefuseVolume", "WarningSoftVolume", "WarningImmediateVolume"):
    p.put(key, 101, block=True)                            # automatic
  print("accord 9g params set:")
  for key in ("LongitudinalPersonality", "DisengageOnAccelerator", "Mads", "HondaLowSpeedPedal", "CustomPersonalities", "QuietMode"):
    print(f"  {key} = {p.get(key, return_default=True)!r}")


if __name__ == "__main__":
  main()
