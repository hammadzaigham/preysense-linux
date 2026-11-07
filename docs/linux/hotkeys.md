# Predator and Turbo keys

Predator toggles PreySense immediately. Rapid presses toggle only; they never
select Turbo. There is no delayed double-press action. The separate physical
Turbo key cycles Eco → Quiet → Balanced → Performance → Turbo → Eco on both
AC and battery. Firmware can reject unsupported requests.

With the current driver, native Predator and shortcut counters notify the app
through sysfs/epoll and a Qt socket notifier. There is no25ms polling timer in
that path. Older drivers retain a compatible polling fallback. Vendor HID reports
are merged with native ownership to avoid duplicate toggles; an80ms Predator
bounce filter and350ms Turbo debounce suppress repeated reports.

Predator+1–5 select modes and Predator+R toggles the overlay. No global input grab
or ordinary key identity log is used. Firmware owns brightness keys; the app
does not monitor or replay brightness-key activity. The app slider is independent.

Tests cover immediate toggles, rapid presses, debounce, native/HID duplicates,
modifier ownership, event notifications and shutdown cleanup. Synthetic tests do
not substitute for a physical button check on another laptop model.
