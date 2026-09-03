"""Wrappers for the external tools themey shells out to.

**xdg-open** (preview auto-open). Suppressed when:
  - SSH_CONNECTION env var is set (running over SSH, T-08-05)
  - Both DISPLAY and WAYLAND_DISPLAY are unset (headless)
  - xdg-open is not on PATH

Uses subprocess.Popen (NOT run/check_call) so the browser launch does not
block the CLI from returning.

**xcursorgen** (XCursor binary assembly, xorg-xcursorgen package). Unlike
xdg-open this one is load-bearing — there is no pure-Python XCursor writer
— so callers ask :func:`xcursorgen_available` first and skip the whole
cursor stage with a note when it is absent (graceful degradation, see
``generate/cursors.py``). ``xcursorgen`` reports some failures by exiting 0
and producing nothing, so :func:`run_xcursorgen` verifies the output file
exists and is non-empty rather than trusting the return code alone.

**waifu2x-ncnn-vulkan** (``--upscale waifu2x``, nihui's CNN upscaler).
Optional like xdg-open, not load-bearing like xcursorgen: when it is
missing ``pipeline.convert`` falls back to hqx and records an
``upscale:`` note, so a conversion never fails for want of it.

Two things it needs, and BOTH have to be checked. Upstream ships the
binary and its ``models-*`` directories as flat siblings in one folder,
and the tool resolves its ``-m models-cunet`` default against the **cwd**
— so an install that copied only the executable to ``/usr/local/bin``
leaves the binary on PATH and the models nowhere, which is the state a
fresh install usually lands in. :func:`waifu2x_available` therefore
tests for a usable model directory too, :func:`waifu2x_unavailable_reason`
says which half is missing so the note can name it, and
:func:`run_waifu2x` always passes an explicit ``-m``, never trusting cwd.
Model discovery is an ordered probe: ``$THEMEY_WAIFU2X_MODELS`` (either
the parent of the ``models-*`` dirs or one model dir itself), then the
binary's own directory, then ``/usr/local/share/waifu2x-ncnn-vulkan``,
then ``/usr/share/waifu2x-ncnn-vulkan``.

Device selection is waifu2x's own ``-g auto`` unless ``$THEMEY_WAIFU2X_GPU``
pins an index (20/20 runs picked the discrete GPU here, and warm software
rendering was only 2x slower, so auto is a fine default). The genuinely
slow case is the FIRST run against a device, which compiles its shader
pipelines — 36s vs 1.7s warm, measured — hence the generous timeout and a
timeout message that quotes the device banner.

A launch that dies on a SIGNAL is retried (``WAIFU2X_ATTEMPTS``); one that
exits non-zero, or times out, is not. That split is the whole point: the
crash is a transient Vulkan device-creation failure in the driver, which
the very next launch of the same input survives, while a non-zero exit is
the tool telling us the arguments are wrong.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from pathlib import Path

from PIL import Image

log = logging.getLogger(__name__)

XCURSORGEN = "xcursorgen"
XCURSORGEN_TIMEOUT_SECONDS = 60

WAIFU2X = "waifu2x-ncnn-vulkan"

# A hang guard, NOT a performance budget, and it has to clear the one
# legitimately slow case: the first run against a given Vulkan device
# compiles its shader pipelines. Measured 2026-09-02 on an idle machine,
# one 124x179 part: 36.2s cold vs 1.70s warm on the same device (the
# compile lands in ~/.cache/mesa_shader_cache). Only the first image of
# the first run pays it, but 120s left barely 3x headroom over a measured
# legitimate cold start — too close on a slower GPU or a loaded machine,
# and chris hit a 120s timeout 2026-09-02 that never reproduced warm.
WAIFU2X_TIMEOUT_SECONDS = 300

# Both are constants so swapping them for a look is a one-line edit.
# E16 art is 3D-rendered chrome rather than the anime cels waifu2x was
# trained on, so ``models-upconv_7_photo`` is the obvious A/B; and ``-n
# -1`` (denoise off) is the one to try if a theme's intentional dither
# reads as noise the model smooths away.
WAIFU2X_MODEL = "models-cunet"
WAIFU2X_NOISE = 0

# Where to look for ``models-<name>``, in order. The env var comes first
# so a developer can point at a source checkout without installing.
WAIFU2X_MODELS_ENV = "THEMEY_WAIFU2X_MODELS"

# waifu2x picks its Vulkan device with -g auto, which was right in 20/20
# runs here. This pins an index (from waifu2x's own stderr banner) for a
# machine where it is not — measured 2026-09-02, warm, on one 124x179 E16
# part: RTX 3070 0.85s, llvmpipe 1.70s. Note that gap is only 2x, NOT the
# reason a run goes slow; see WAIFU2X_TIMEOUT_SECONDS for what is.
WAIFU2X_GPU_ENV = "THEMEY_WAIFU2X_GPU"

# Relaunch budget for a CRASHED run, and only a crashed one.
#
# Measured 2026-09-02 on chris's RTX 3070 (driver 580.173, Vulkan 1.4.341,
# two devices enumerated: the NVIDIA one and llvmpipe): 2 of 270 otherwise
# identical launches died with ncnn printing ``vkCreateDevice failed -3``
# — VK_ERROR_INITIALIZATION_FAILED — after which it returns a VulkanDevice
# it never created and waifu2x dereferences it, so the process dies on
# SIGSEGV (returncode -11). ~0.7% per launch is harmless in isolation and
# fatal in aggregate: themey fires one launch per distinct source image,
# ~40 for Aliens between the decoration, the Plasma Style and the
# wallpapers, so a quarter of all converts hit it. Pinning the device with
# $THEMEY_WAIFU2X_GPU did not clear it (0/150 against 2/270 is not a
# difference at this rate), and the failure is not ours to fix inside a
# third-party binary — but it IS transient: the next launch of the same
# input succeeded every time, so three attempts take the per-image odds to
# ~3e-7. The delay is a courtesy to whatever driver state is settling, not
# a measured requirement.
WAIFU2X_ATTEMPTS = 3
WAIFU2X_RETRY_DELAY_SECONDS = 0.5
_WAIFU2X_MODEL_ROOTS = (
    Path("/usr/local/share/waifu2x-ncnn-vulkan"),
    Path("/usr/share/waifu2x-ncnn-vulkan"),
)


class XcursorgenError(Exception):
    """The xcursorgen subprocess failed or produced no usable output."""


class Waifu2xError(Exception):
    """The waifu2x subprocess failed or produced no usable output."""


def open_preview_unless_headless(html_path: Path) -> bool:
    """Open *html_path* in the user's browser unless headless/SSH is detected.

    Returns True if the browser was launched, False if suppressed.
    Caller should print the path on False so the user can open manually.
    """
    if os.environ.get("SSH_CONNECTION"):
        return False
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        return False
    xdg = shutil.which("xdg-open")
    if not xdg:
        return False
    subprocess.Popen(
        [xdg, str(html_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return True


def xcursorgen_available() -> bool:
    """True when the ``xcursorgen`` executable is on PATH."""
    return shutil.which(XCURSORGEN) is not None


def run_xcursorgen(config: Path, out: Path, image_dir: Path) -> Path:
    """Assemble the XCursor binary described by *config* into *out*.

    *config* holds one ``<size> <xhot> <yhot> <png>`` line per nominal
    size; the PNG names are resolved relative to *image_dir* (``-p``).

    Returns *out*. Raises :class:`XcursorgenError` when the tool is absent,
    times out, exits non-zero, or leaves no non-empty output file — with
    the tail of stderr attached so the caller can report why.
    """
    exe = shutil.which(XCURSORGEN)
    if exe is None:
        raise XcursorgenError(f"{XCURSORGEN} is not on PATH")
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [exe, "-p", str(image_dir), str(config), str(out)]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=XCURSORGEN_TIMEOUT_SECONDS
        )
    except subprocess.TimeoutExpired as exc:
        raise XcursorgenError(
            f"{XCURSORGEN} timed out after {XCURSORGEN_TIMEOUT_SECONDS}s on {config}"
        ) from exc
    tail = proc.stderr.strip()[-500:]
    if proc.returncode != 0:
        raise XcursorgenError(
            f"{XCURSORGEN} exited {proc.returncode} on {config.name}: {tail}"
        )
    if not out.is_file() or out.stat().st_size == 0:
        raise XcursorgenError(
            f"{XCURSORGEN} produced no output (or an empty file) at {out}: {tail}"
        )
    return out


def _is_model_dir(path: Path) -> bool:
    """True when *path* looks like a waifu2x ``models-*`` directory.

    ncnn model dirs are a flat set of ``*.param`` / ``*.bin`` pairs; one
    ``.param`` is enough to tell a real model dir from an empty stub. The
    binary itself reports a missing weight file clearly, so a finer check
    here would only duplicate its error.
    """
    return path.is_dir() and any(path.glob("*.param"))


def waifu2x_models_dir(model: str = WAIFU2X_MODEL) -> Path | None:
    """Return the directory holding *model*'s weights, or None.

    Probes, first hit wins: ``$THEMEY_WAIFU2X_MODELS`` (accepted both as
    the parent of the ``models-*`` dirs and as one model dir itself, since
    either is a reasonable thing to point it at), the directory the
    executable lives in — where upstream ships them as flat siblings —
    then the two ``share/`` locations a packaged install would use.
    """
    env = os.environ.get(WAIFU2X_MODELS_ENV)
    roots: list[Path] = []
    if env:
        candidate = Path(env)
        if _is_model_dir(candidate / model):
            return candidate / model
        if _is_model_dir(candidate):
            return candidate
    exe = shutil.which(WAIFU2X)
    if exe is not None:
        roots.append(Path(exe).resolve().parent)
    roots.extend(_WAIFU2X_MODEL_ROOTS)
    for root in roots:
        if _is_model_dir(root / model):
            return root / model
    return None


def waifu2x_unavailable_reason(model: str = WAIFU2X_MODEL) -> str | None:
    """Why waifu2x cannot run, as a sentence — or None when it can.

    The two halves fail independently and a note that says only "waifu2x
    is unavailable" sends the reader looking for the wrong thing, so the
    binary-present-models-missing case names the directories that were
    searched.
    """
    if shutil.which(WAIFU2X) is None:
        return f"{WAIFU2X} is not on PATH"
    if waifu2x_models_dir(model) is None:
        searched = ", ".join(str(r / model) for r in _WAIFU2X_MODEL_ROOTS)
        return (
            f"{WAIFU2X} is on PATH but its {model} weights are not "
            f"(looked beside the binary, in {searched}, and at "
            f"${WAIFU2X_MODELS_ENV})"
        )
    return None


def waifu2x_available(model: str = WAIFU2X_MODEL) -> bool:
    """True when both the ``waifu2x-ncnn-vulkan`` binary and *model* are found."""
    return waifu2x_unavailable_reason(model) is None


def run_waifu2x(
    src: Path, out: Path, factor: int, model: str = WAIFU2X_MODEL
) -> Path:
    """Upscale the PNG at *src* by *factor* into *out*, returning *out*.

    *factor* must be one of waifu2x's supported powers of two; the tool
    rejects anything else ("invalid scale argument") rather than rounding.

    A launch killed by a signal is relaunched up to ``WAIFU2X_ATTEMPTS``
    times — see that constant for the measured transient this exists for.
    Every other failure is reported on the first try.

    Raises :class:`Waifu2xError` when the binary or its weights are
    absent, the run times out or exits non-zero (crashes having exhausted
    their retries), or the output is missing, empty, or not exactly
    *factor* times the source dimensions — the same output-verification
    discipline :func:`run_xcursorgen` uses, since an exit code alone does
    not prove the pixels arrived.
    """
    exe = shutil.which(WAIFU2X)
    if exe is None:
        raise Waifu2xError(f"{WAIFU2X} is not on PATH")
    models = waifu2x_models_dir(model)
    if models is None:
        raise Waifu2xError(waifu2x_unavailable_reason(model))
    with Image.open(src) as probe:
        expected = (probe.width * factor, probe.height * factor)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        exe,
        "-i", str(src),
        "-o", str(out),
        "-s", str(factor),
        "-n", str(WAIFU2X_NOISE),
        "-m", str(models),
    ]
    gpu = os.environ.get(WAIFU2X_GPU_ENV)
    if gpu:
        cmd += ["-g", gpu]
    for attempt in range(1, WAIFU2X_ATTEMPTS + 1):
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=WAIFU2X_TIMEOUT_SECONDS
            )
        except subprocess.TimeoutExpired as exc:
            # Keep whatever stderr arrived before the kill. waifu2x prints
            # its Vulkan device banner the moment it starts, so this says
            # which device was chosen and whether it got as far as loading
            # the model — without it a timeout says nothing about WHY, which
            # is what stalled the 2026-09-02 investigation.
            #
            # Not retried, unlike a crash: the budget is 300s an attempt,
            # so three of them would spend a quarter of an hour restating
            # that the machine is wedged.
            partial = exc.stderr or ""
            if isinstance(partial, bytes):
                partial = partial.decode("utf-8", "replace")
            tail = partial.strip()[-500:]
            detail = f": {tail}" if tail else ""
            raise Waifu2xError(
                f"{WAIFU2X} timed out after {WAIFU2X_TIMEOUT_SECONDS}s on "
                f"{src.name}. The banner below names the Vulkan devices it "
                f"found; pin one with ${WAIFU2X_GPU_ENV}=<index> if it chose "
                f"badly{detail}"
            ) from exc
        tail = proc.stderr.strip()[-500:]
        if proc.returncode == 0:
            break
        # subprocess reports a signal death as -N. That is the transient
        # Vulkan-init crash (see WAIFU2X_ATTEMPTS) and nothing else here
        # produces one; an ordinary non-zero exit is the tool REJECTING
        # the arguments ("invalid scale argument" is exit 255) and would
        # say the same thing three times over.
        crashed = proc.returncode < 0
        if not crashed or attempt == WAIFU2X_ATTEMPTS:
            tries = f" after {attempt} attempts" if attempt > 1 else ""
            raise Waifu2xError(
                f"{WAIFU2X} exited {proc.returncode} on {src.name}{tries}: {tail}"
            )
        log.warning(
            "%s crashed (signal %d) on %s, attempt %d of %d; retrying",
            WAIFU2X, -proc.returncode, src.name, attempt, WAIFU2X_ATTEMPTS,
        )
        time.sleep(WAIFU2X_RETRY_DELAY_SECONDS)
    if not out.is_file() or out.stat().st_size == 0:
        raise Waifu2xError(
            f"{WAIFU2X} produced no output (or an empty file) at {out}: {tail}"
        )
    with Image.open(out) as got:
        size = (got.width, got.height)
    if size != expected:
        raise Waifu2xError(
            f"{WAIFU2X} returned {size[0]}x{size[1]} for {src.name}, "
            f"expected {expected[0]}x{expected[1]} at -s {factor}"
        )
    return out
