# GPU boot-mode selection

The dashboard uses Auto, Hybrid and NVIDIA GPU Only. These are firmware boot settings; live Advanced Optimus display handover is unavailable.

A PreySense-style Save/Cancel dialog appears when moving from Auto or Hybrid to NVIDIA GPU Only, or back from NVIDIA GPU Only to either option. Moving between Auto and Hybrid does not open this dialog. Cancel and Escape leave firmware unchanged. Saving verifies firmware readback, and applies at the next restart; PreySense never restarts the laptop automatically. Clicking the already saved setting does nothing.

The selected tile describes the saved firmware setting, which may differ from the display routing of the current session until reboot. NVIDIA GPU Only is disabled if no supported driver is bound to the discrete GPU. A missing NVIDIA runtime driver can reflect Secure Boot rejecting an installed module; see [NVIDIA diagnosis](nvidia-diagnosis.md).
