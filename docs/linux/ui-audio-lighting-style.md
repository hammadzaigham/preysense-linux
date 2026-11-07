# Audio and Lighting style alignment

The controls keep their existing Linux behavior. This styling pass follows the
Windows sources rather than adding a different dashboard or changing settings.

- All Audio and Lighting windows use the shared30px `WindowTitleBar`,16px app
  icon,12px brand/subtitle and one close control.
- Root layouts have no extra margins. Content uses `WindowContentMargin`:
 14px left/right,10px top,8px bottom.
- Audio Apply/Save and reset footers use the original34px button height and
 14/10/14/16px footer margins, with4px between buttons. Original setting-action
  buttons are28px tall; general actions are30px.
- Audio preset dropdown is220px, section headings13px. Audio controls still use
  the same save/readback logic; no DSP/service behavior was changed.
- Lighting mode selectors use154px; preset selectors210px. Color wheels are
 140px, with centered22px swatch and80×26px hex editor matching the XAML.
- Palette-dependent rules use the existing tokens, including the Linux options
  separators and focus outlines. No fixed white separator is introduced.
- Lighting keeps the requested live changes and has no Apply/status section.
  Navigation/construction still sends no commands; user changes retain80ms
  debouncing. The swatch is only a visual preview of the existing color value.

References: `Views/DtsAudioWindow.xaml`, `Views/CustomAudioWindow.xaml`,
`Views/DtsEqualizerWindow.xaml`, `Views/KeyboardWindow.xaml`,
`Styles/Spacing.xaml`, `Styles/Typography.xaml`, `Styles/Controls.xaml` and
`Controls/WindowTitleBar.xaml` under `PreySense.Frontend`.

Focused mocked tests cover existing behavior plus title/content/footer geometry.
Dark and light renders are inspected. Font rasterization remains dependent on the
available Linux font; these checks do not assert pixel identity with Windows.
