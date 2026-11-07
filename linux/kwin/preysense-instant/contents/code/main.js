// KWin scripted-effect grab roles prevent other animation effects handling this
// application's windows. No global effects or animation speeds are changed.
function isPreySense(window) {
    var desktop = String(window.desktopFileName || "").toLowerCase();
    if (desktop === "preysense" || desktop === "preysense.desktop") return true;
    var tokens = String(window.windowClass || "").toLowerCase().split(/\s+/);
    return tokens.indexOf("preysense") !== -1 || tokens.indexOf("preysense.desktop") !== -1;
}
function makeInstant(window) {
    if (!isPreySense(window)) return;
    [Effect.WindowAddedGrabRole, Effect.WindowClosedGrabRole,
     Effect.WindowMinimizedGrabRole, Effect.WindowUnminimizedGrabRole].forEach(function(role) {
        effect.grab(window, role, true);
    });
}
effects.windowAdded.connect(makeInstant);
effects.windowClosed.connect(makeInstant);
if (effects.windowShown) effects.windowShown.connect(makeInstant);
if (effects.windowMinimized) effects.windowMinimized.connect(makeInstant);
if (effects.windowUnminimized) effects.windowUnminimized.connect(makeInstant);
// Also cancel already-owned scale/fade transitions after enabling the effect.
effects.stackingOrder.forEach(makeInstant);
