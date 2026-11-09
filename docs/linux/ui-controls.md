# Linux lighting wheel and fan graph

The lighting wheel keeps the original hue/saturation disk, white center and outlined
selected color marker. Its cache follows display scaling. Arrow keys adjust hue or
saturation when focused.

The fan graph matches the Windows stage editor: X is each stage's entry °C
(40–100), Y is duty %, with a lead-in floor and step curve. Clicking a point
selects it without changing values. Dragging edits duty (and temperature when
clearly horizontal). Adjacent points keep duties nondecreasing and temperatures
unique. Blank graph clicks do not change values. Left/right selects a point;
up/down changes duty by one percent. Temp / Duty / RPM rows mirror Windows.

Mocked Qt tests exercise wheel selection, actual-point hit testing, relative drag,
monotonic bounds and keyboard edits without writing fan or lighting hardware.

## Lighting window parity

`lighting_ui.build_lighting_window(window)` runs after the original Linux control
construction and reuses the existing Apply, brightness, timeout and API fields.
The visible order follows `KeyboardWindow.xaml`: Brightness, Backlight Timeout,
Keyboard/Logo tabs, then Static/Dynamic/Software controls, zone sync, original
preset names and palettes, zone selection, wheel/hex, effect and speed. The Logo
tab follows Logo Backlight, Sync With Keyboard, Effect Mode, presets, wheel/hex
and Animation Speed. All original zone and cover palette values are copied from
`MainViewModel.Lighting.cs`.

Selection and editing remain drafts until Apply. Target state survives tab changes.
The speed slider displays 0–100 percent and translates to the supported Linux
0–10 API. The timeout exposes only the verified Never/30-second values; Windows'
0–120-second timer is not claimed. Windows Ripple, Snake and Disco are disabled
because their hardware mappings are unverified. Additional supported Linux
hardware effects appear after the original list. The explicit Apply action and
hardware status remain Linux UI additions.

## Settings consolidation and slider steps

The main Advanced button is removed. Its remaining source-profile and native power controls are now in Settings. There is no extra Advanced window. Pointer input, wheel input and keyboard increments use the original Windows slider grids: brightness and effect speed25; timeout10seconds (Page30); overlay scale5%; opacity10%; fan delay1second; Tau one index at a time; audio enhancement1point (Page5), EQ1dB. Inputs clamp to their original ranges. Existing backend validation still applies. Main/footer icons use16logicalpixels with native image backing; title-bar icons16, performance SVGs18, GPU icons20. The close button has a7px top-right radius matching its shell.
