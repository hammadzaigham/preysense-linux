# DTS:X Ultra / AcerUltraX integration

PreySense integrates [AcerUltraX](https://github.com/fawaz7/AcerUltraX), the MIT project
by Fawaz Al-Ghzawi described in [this Reddit post](https://www.reddit.com/r/AcerPredatorHelios/comments/1xcis5k/i_got_acers_dtsx_ultra_sound_working_natively_on/).
It loads Acer's original DTS engine natively and routes audio with PipeWire. No
Wine, Rust compiler, GTK development package or package repository was added for
this integration. The source reference is in `/home/hammad/Development/AcerUltraX`.

## Setup and retained files

The v0.1.4 x86_64 tarball was checked against its published SHA256SUMS and installed
per-user using the upstream installer. Then:

```sh
acerultrax-cli detect
acerultrax-cli setup
acerultrax-cli autostart on
```

The audio chip is Realtek ALC245, subsystem `10251871`. The project marks this model
experimental, although its matching tuning imports and the engine runs. Setup
imports 26 tuning files, 552 headphone profiles, a spatial encoder and 17 presets.
The large Acer download archives are cleaned by setup; retained model files occupy
about 19 MB. Binaries/settings live under the user's `.local` / `.config` locations.
No DTS/Acer binary is committed into the PreySense repository.

## Controls

Open **Advanced → DTS:X Ultra Settings**. Supported profiles include Off, Music,
Movie, Voice, Game1–3, Custom Audio and Plain. Off retains the engine's protected
speaker behavior; Plain is the unprocessed comparison path. Per-output selection,
Bluetooth/headphone following and routing are handled by AcerUltraX.

The window exposes DTS power, spatial sound, loudness-matched comparison and the
headphone model catalog. The custom profile editor offers ten EQ bands from 31 Hz
to 16 kHz (−15 to +15 dB), bass, dialogue, virtual surround and loudness controls.
Save and Apply creates an AcerUltraX profile and selects it for the current output.

PreySense uses the documented newline-delimited JSON socket at
`$XDG_RUNTIME_DIR/acerultrax.sock`, with timeouts and bounded replies. It sends only
the supported typed commands. It does not invoke a shell or arbitrary user command.

## Verification and limitations

All built-in modes, spatial enable/readback, comparison and a temporary custom EQ
profile passed live service checks. The temporary profile was removed and Music
restored. An offline 48,000-frame stereo WAV was processed by the actual DTS engine;
it produced a non-empty, changed output. No sound was played for this test and no
independent listening or bit-for-bit Windows comparison is claimed for this model.

The user service continues processing after PreySense exits. To inspect or disable:

```sh
acerultrax-cli status
systemctl --user status acerultrax.service
acerultrax-cli autostart off
```

Disabling its autostart stops the daemon and returns audio to normal routing.
AcerUltraX is independently installed; PreySense removal does not delete it.

## Room presets and reset

Linux Audio Options exposes the engine's supported Entertainment, Game, Sports and
Entertainment 2022 room presets. Reset to Factory Defaults restores the selected
profile's base DTS mode without deleting a user profile: custom tweaks are cleared,
while built-in profiles are simply reselected because their names are reserved.
A temporary Game-room profile passed live save/readback and reset checks, then was
removed and the original audio profile restored.

Front/Wide/Traditional now use the actual DTS Eagle stereo-image control through
the bundled MIT AcerUltraX extension. The engine's public table reports
Eagle-Front, Eagle-Wide and Eagle-Off; Traditional selects Eagle-Off (stereo
imaging bypass), independently of the surround room. Treble Enhance remains
unavailable. The 10-band equalizer is separate from stereo imaging.
Per-output service changes refresh the selected output/profile when the device
changes; editing a dropdown alone does not switch sound until Apply.

## Dialogs and Windows layout

DTS keeps the original separate Sound Mode, Customize Sound Profile and Equalizer
navigation. Custom Audio follows the Windows Stereo Sound, Enhancements, Treble,
Bass, Dialog and Volume Smoothing order. Stereo choices are selectable when the audio service is available and saved
with the custom profile; Treble remains unavailable. Linux surround/room and profile name/base
fields are in Linux Audio Options, preserving the original custom dialog order.

The equalizer retains ten vertical bands and keeps the original Windows ±10 dB
range (the backend separately accepts ±15 dB). Both editor footers follow the
original Apply, Save order: both persist and activate the named profile; Apply
keeps the editor open. Save closes only after the active profile and a fresh
service profile-catalog readback match the submitted values. Failed or unavailable
service responses leave the editor open. This follows Windows' actual handlers
(`Commit(close: false)` and `Commit(close: true)`). Reset is exposed only in the
main DTS window. The equalizer master switch is disabled with an explanation
because independent equalizer bypass is not exposed by the Linux service.

UI checks use a fake audio service and verify typed commands, no-write selection,
resets, room loading, disabled enhancement serialization and unavailable-state
controls. They establish UI behavior, not audible Windows DSP equivalence.

The main DTS dialog uses the original 480-pixel width. Linux service power,
spatial routing, comparison and headphone-model selection are in the separate
Linux Audio Options dialog, reached below the original profile/reset controls.

## DTS window preset labels

The480px DTS page now applies a selected preset immediately, matching Windows; there is no extra main Apply button. It labels the current output and shows Customize Sound Profile and Equalizer only for Custom/custom profiles. Display names map to unchanged service tokens: Game - Immersive→Game1, Game - Competitive→Game2, Game - Entertainment→Game3, Custom→Custom Audio. Preset readback updates block selection signals to avoid reapplying a setting from telemetry. Windows Auto routing is not claimed implemented by this label/layout change.


## Stereo backend installation

`setup_audio.py` verifies and installs the bundled x86_64 AcerUltraX daemon with
PreySense's stereo extension, including when upgrading an existing installation.
It restarts only the per-user audio daemon when its binary changes; existing
DTS tuning files, profiles and selected output are retained. Repeated setup does
not replace an identical daemon. The upstream CLI remains pinned and checksummed.
The daemon's MIT license, source commit, patch and rebuild instructions ship in
`linux/audio_backend/`; no Rust toolchain or development packages are needed on
the installed system. Source and RPM installations both include this payload.

Verification covered three engine-control mapping tests, UI selection/save/reload,
and live temporary profiles for all three choices with successful service
readback and no engine errors. The original profile was restored afterward.
This verifies control application, not subjective audible equivalence.
