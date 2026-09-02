# Bundled E16 config files

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

`e16_actionclasses.cfg` is a verbatim copy of `config/actionclasses.cfg`
from the same release — the stock `__ACLASS` blocks. E16 falls back to it
when a theme ships no `actionclasses.cfg` of its own
(`config.c` `ConfigFileLoad` -> `ConfigFileFind` -> `FindFile`), which is
how a 2009 theme binds a border part to `ACTION_WINDOW_SLIDEOUT` or
`ACTION_MAXH` without ever defining them. `analyze/aclasses.py` reads it
for the name -> `__A_*` verb table that gives such a part its button;
themey layers it UNDER the theme's own blocks rather than skipping it when
the theme has its own file, so a stock name the theme omits still resolves.

License: `E16_COPYING` (MIT-style, Carsten Haitzler, Geoff Harrison, Kim
Woelders and contributors). The copyright notice is preserved there as
that license requires.
