# Test fixture attribution

`tests/fixtures/` contains five real Enlightenment DR16 `.etheme` archives.
They are **not** part of themey and are **not** covered by themey's MIT
license. They are third-party artwork from roughly 1999–2009, included here
solely as test fixtures for a format converter: the parser, the geometry
resolver, and the snapshot tests need real-world input, and synthetic archives
do not exercise the grammar quirks these files contain.

Each archive is included **unmodified**, byte-for-byte as published.

## Source

All five were downloaded from the public E16 theme library at
`https://themes.effx.us/packages/e16/<Name>.etheme` — the theme collection the
Enlightenment DR16 project itself points at. Provenance was verified by size:

| Fixture | Bytes | Upstream URL |
|---|---|---|
| `Aliens.etheme` | 2,186,738 | https://themes.effx.us/packages/e16/Aliens.etheme |
| `e13.etheme` | 859,193 | https://themes.effx.us/packages/e16/e13.etheme |
| `LiteGnome.etheme` | 615,911 | https://themes.effx.us/packages/e16/LiteGnome.etheme |
| `Mac3D.etheme` | 271,844 | https://themes.effx.us/packages/e16/Mac3D.etheme |
| `OPENSTEP.etheme` | 17,305 | https://themes.effx.us/packages/e16/OPENSTEP.etheme |

(`tiny.etheme` and everything under `malicious/` are synthetic archives written
for this repository and carry no third-party content.)

## Authors and terms

Terms below are whatever the archives themselves state, read out of their
`ABOUT/` directories. Where an archive states nothing, this file says so
rather than guessing. **"No stated terms" means exactly that** — no permission
was granted, and none is implied here.

### `Mac3D.etheme`

By **Mark J Eaton** (HeTTaR), `hettar@uq.net.au`. Some small graphics and
cursors are credited to Raster (Carsten Haitzler).

`ABOUT/Authors` grants redistribution explicitly:

> You are free to use this theme yourself. You are free to give this theme to
> other people. You are free to include this theme on CD's or pretty much
> where ever you want to. All I ask is that this file and the headers in the
> \*.cfg files remain in place, you don't claim credit for my work and that
> you tell me about it so that I can feel good ;o).

The archive is included whole, so `ABOUT/Authors` and the `.cfg` headers
remain in place, and no credit for the work is claimed.

### `OPENSTEP.etheme`

By **Jesse Kaufman**, based on *eStep_New* by **Greg Mindrum**. Credits only —
**no stated terms**.

### `e13.etheme`

By **Ben Frantzdale**, a port of the E13 default theme to E 0.16.
**No stated terms.**

### `Aliens.etheme`

Ported by **Michiel** (`mic@cistron.nl`) from **Wrex's** DR 0.13 Aliens theme.
**No stated terms.**

`ABOUT/MAIN` additionally states:

> The original Alien concept is a creation of H.R. Giger. (www.hrgiger.com).
> Also some of his paintings are featured in this theme.

That is third-party artwork inside a third-party theme, used without any
stated permission by the theme's own author. It is noted here plainly; nothing
in this repository should be read as a claim that its inclusion is licensed.

### `LiteGnome.etheme`

`ABOUT/` is empty — the archive contains no author or license information at
all. **No stated terms.**

## Removal

If you are an author or rights holder of any of these themes (or of artwork
inside one) and would prefer it not be redistributed here, email
**c0re@merle.io** and it will be removed. No argument, no process.

## A note on generated metadata

themey's generated KPackage metadata hardcodes `"License": "GPL"` —
`generate/lookandfeel.py:134`, `generate/plasmastyle.py:1038`, and
`generate/qmldeco/package.py:50`. This is an arbitrary placeholder: the real
terms of a 2000-era E16 theme are usually unknown (see above), and no source
theme's license is inspected or propagated. The value is retained only for
snapshot stability, and is **not** an assertion about any source theme's
actual license.
