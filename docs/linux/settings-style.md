# Settings and Advanced styling

The Linux Settings and Advanced windows retain their current working controls
and the user's explicit Linux removals. Their styling follows the repository's
`AdvancedSettingsWindow.xaml`, `AdvancedWindow.xaml`, `WindowTitleBar.xaml`,
`Styles/Controls.xaml`, `Styles/Spacing.xaml` and `Styles/Typography.xaml`:

- 540px width; 30px shared title bar, 16px app icon and 30px close button.
- Content margins14px left/right,10px top,8px bottom.
- Existing setting rows supply4px top/bottom margins; no extra12px gap is added
  between every row. Standard toggles remain56×28; theme/battery toggles92×28.
- 12px body labels and semibold13px section headings inherit theme colors.
- Section separators use the shared palette and12px vertical margins.
- Content-sized height is recalculated before first painting, avoiding600px
  fixed-height empty space and unnecessary scrollbars after theme/font polish.

The Linux native GPU-offset helper keeps its verified Apply/Restore actions and
explanatory text. It now uses the same frameless title bar,540px width,90×28 value
editors and34px action buttons. It remains an explicit current-session helper;
this styling change does not change power writes or introduce another firmware
installation/defaults UI.

The documentation viewer remains available because Linux documentation was
explicitly requested. Its760×660 reading area and Back/Home navigation are
preserved; a shared title bar replaces the duplicate native/inner close controls,
and navigation buttons use28px row height. These Linux-only diagnostic/document
windows have no identical Windows counterpart, so they reuse the original shell
without claiming an exact source-window mapping.

Four focused styling/action tests and the existing six platform-window tests
pass. Mocked dark/light Settings, tuning and documentation renders
were inspected; this validation performs no hardware writes.
