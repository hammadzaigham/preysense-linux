# PreySense AcerUltraX stereo extension

Upstream MIT source: https://github.com/fawaz7/AcerUltraX
Base commit: 117ba002083274231d5eceea8626184a89d02e34
Version: 0.1.4 plus stereo.patch

The bundled x86_64 daemon adds a typed stereo tweak and mode-default readback.
It applies the actual Eagle-Stereo Mode control to SFX and MFX, without mapping
stereo choices to unrelated surround rooms. Front=Eagle-Front, Wide=Eagle-Wide,
Traditional=Eagle-Off (the engine's stereo-imaging bypass). Existing profiles
without this field retain factory defaults. No proprietary DTS files are bundled.

Rebuild on Linux with Rust 1.85+, libclang and PipeWire development headers:

```sh
git clone https://github.com/fawaz7/AcerUltraX
cd AcerUltraX
git checkout 117ba002083274231d5eceea8626184a89d02e34
git apply /path/to/PreySense/linux/audio_backend/stereo.patch
cargo test -p acerultrax-daemon config::tests
cargo build --release -p acerultrax-daemon
strip target/release/acerultrax-daemon
```

Copy the daemon here and update SHA256 in setup_audio.py after rebuilding.
