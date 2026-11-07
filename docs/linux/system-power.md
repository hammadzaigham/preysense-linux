# Linux system power profile

Confirmed Acer performance modes automatically map to the existing Linux
power-profile service. Eco/Quiet select `power-saver`, Balanced selects `balanced`,
and Performance/Turbo select `performance`. This complements the Acer firmware
mode rather than treating CPU watts or fan settings as system power saving.
There is no separate Energy Saver on Battery switch.

`SystemPower.sync(mode)` accepts confirmed firmware integers, numeric strings or
canonical names, including the first valid startup snapshot. It reads the actual
profile, attempts one change per confirmed OEM mode transition, and verifies
readback. It never writes from a pending UI request. Repeated snapshots preserve
manual KDE profile changes instead of continually reasserting PreySense's choice.
A new daemon owner permits one fresh attempt; unavailable/rejected profiles remain
explicit errors rather than claiming success. No packages are installed.

The implementation uses a persistent Qt system-bus connection to
`org.freedesktop.UPower.PowerProfiles`, path `/org/freedesktop/UPower/PowerProfiles`.
`Properties.Get` reads ActiveProfile and `Properties.Set` sends a string wrapped
in a D-Bus variant. The installed service may be power-profiles-daemon or a
compatible provider such as tuned-ppd. Unsupported systems remain unavailable.

Before its first owned change, PreySense records the previous system profile.
On shutdown it restores that profile only when the service owner and current
profile still match its last verified write. A detected external profile edit
invalidates ownership, preserving the user's newer preference. Daemon restarts
discard old ownership and establish a new baseline when a new write succeeds.
A profile changed away and back between observations cannot be distinguished
from an unchanged value; ownership is based on observed readback.

Construct `SystemPower` in the worker, or construct it without a client then make
its first call there; lazy client creation avoids contacting D-Bus in the UI
thread. Poll with confirmed `profile` snapshots. `snapshot()` returns mode,
target, actual profile, availability, ownership and error. `shutdown()` releases
ownership by conditionally restoring the saved profile. No continuous timer or
subprocess performs profile writes.

Eight injected-client tests cover mapping, startup, one-attempt behavior,
readback failures, manual changes, restoration, daemon restart and invalid input.
A private session-bus mock verified the real Qt Get/Set variant transport and
readback; it changed no system profile. A read-only system-bus check confirmed
that this machine exposes ActiveProfile through the compatible service.
