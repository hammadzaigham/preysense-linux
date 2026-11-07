# Confirmed mode notification

`ModeToast(owner).show_mode(mode)` displays the original Windows performance-mode
pill. Accepts confirmed firmware bytes 0/1/4/5/6 or Quiet/Balanced/Performance/
Turbo/Eco names. Invalid inputs do not show a notification. This widget performs
no hardware reads or writes; callers must pass a confirmed state change.

The port follows `Views/ModeToastWindow.xaml` and its code-behind: 160–220 logical
pixels wide, 40 high, 20px corners, 18px existing mode icon, 9px text gap and 14px
medium label. Colors follow the source's Eco, Accent, Performance and Turbo
colors. Fade in takes 150ms, the visible hold lasts 1800ms, and fade out takes
250ms. A new confirmed mode cancels the preceding fade/hold and restarts the
notification. The toast centers on the owner's monitor, 72 physical pixels above
its available work area's bottom, accounting for display scale.

Qt tool/no-focus/show-without-activation and transparent-input flags prevent
focus stealing and mouse interception. Final stacking/input policy is controlled
by the desktop compositor. Linux uses the system font fallback for Segoe UI.

Integration: retain one toast per main window. In the existing hardware snapshot
handler, compare valid confirmed `profile` values against the previous confirmed
profile. Seed the initial baseline without showing a toast. On subsequent actual
changes, call `show_mode(profile)`, including firmware/hotkey changes. Do not call
it from the mode-button callback or immediately after a write request. Close the
toast during application shutdown; all timers and animations stop on close.

Three hardware-free tests cover geometry, physical screen offset, nonactivation/
click-through flags, fade/hold/restart lifecycle, invalid input and transparent
rendering. All five modes were rendered together for visual inspection.

The toast intentionally follows the Windows source animation:150ms OutQuad fade-in, then1800ms hold, then250ms InQuad fade-out. Main/control windows remain instant through scoped KWin suppression.
