# Instant windows on KDE

Qt's menu/tooltip animation switches do not disable KWin's own Scale, Fade or
Squash effects. PreySense therefore ships an application-scoped scripted effect
in `linux/kwin/preysense-instant`. It claims the documented KWin open, close,
minimize and unminimize animation roles for exact `preysense` application IDs or
WM_CLASS tokens only. Repeated Wayland show events are included. Other
applications' effects and the global animation speed are unchanged.

`kwin_integration.install_instant_effect()` installs/updates this small package
using the existing `kpackagetool6`, enables only `preysense-instant`, loads it over
KWin D-Bus and verifies `isEffectLoaded`. Call before displaying the first app
window. The installed runtime must include the `linux/kwin/` source directory.
Offscreen and non-KDE sessions do nothing. The original `kwinrc` is saved once as
`~/.config/kwinrc.before-preysense-instant`; restore individual settings rather
than replacing later unrelated desktop changes with this whole backup.

Current-user installation was verified on the development laptop: KWin reports
`preysense-instant` loaded. Tests execute the real effect JavaScript against a
stub KWin API and verify exact application scope and all four role claims.
This proves integration and handler behavior; live visual verification remains
a separate check when opening/restoring the application.

To remove only this integration:

```sh
busctl --user call org.kde.KWin /Effects org.kde.kwin.Effects unloadEffect s preysense-instant
kwriteconfig6 --file kwinrc --group Plugins --key preysense-instantEnabled --delete
kpackagetool6 --type KWin/Effect --remove preysense-instant
```

The role API is documented in the [KWin scripting API](https://develop.kde.org/docs/plasma/kwin/api/).
The installed KDE Scale/Fading Popups sources also honor these grab roles and
cancel their own animations when another effect claims a window.
