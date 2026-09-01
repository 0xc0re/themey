# Bundled E16 macro file

`e16_definitions` is a verbatim copy of `config/definitions` from
Enlightenment DR16 1.0.31 (https://www.enlightenment.org/), the cpp macro
file E16 pipes every theme cfg through (`#include <definitions>`). Themes
never ship it, yet every corpus `menustyles.cfg` (223/223) and many
border/tooltip files use its convenience macros
(`NORMAL_MENU_STYLE_VERTICAL`, `DEFINE_TOOLTIP`, ...).

`parse.py` registers ONLY its function-like macros. Its object-like
`#define`s are E16's numeric config ids (`__BGN 999`, `__NORMAL 402`,
`__ON 1`) and X cursor constants; expanding those would turn themey's
keyword grammar into numbers.

License: `E16_COPYING` (MIT-style, Carsten Haitzler, Geoff Harrison, Kim
Woelders and contributors). The copyright notice is preserved there as
that license requires.
