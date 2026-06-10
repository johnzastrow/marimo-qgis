#!/usr/bin/env bash
#
# qgis-env.sh — provision and diagnose the marimo + QGIS Python environment.
#
# The fragile part of running marimo against PyQGIS is that PyQGIS is a compiled
# C-extension locked to the exact Python build QGIS was compiled against. Pinning
# a hardcoded Python version (e.g. 3.13.7) breaks the moment the OS or QGIS is
# upgraded. This script removes the pin: instead of guessing a version, it asks
# QGIS which interpreter actually loads its bindings, and builds the venv against
# that — so the environment self-heals across upgrades.
#
# Usage:
#   ./qgis-env.sh doctor    Diagnose the environment; suggest exact fixes.
#   ./qgis-env.sh setup     Detect QGIS's Python and (re)create the venv.
#   ./qgis-env.sh path      Print the detected QGIS Python interpreter and exit.
#
# Overridable via environment:
#   QGIS_PYTHON_PATH   PyQGIS bindings dir   (default: /usr/share/qgis/python)
#   PYTHON_CANDIDATES  space-separated interpreters to probe, highest priority first
#   MARIMO_DEPS        packages to install into the venv
#
set -euo pipefail

QGIS_PYTHON_PATH="${QGIS_PYTHON_PATH:-/usr/share/qgis/python}"
MARIMO_DEPS="${MARIMO_DEPS:-marimo pandas numpy matplotlib}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${PROJECT_DIR}/.venv"

# ANSI helpers (disabled when not a TTY).
if [ -t 1 ]; then
    BOLD=$'\033[1m'; RED=$'\033[31m'; GRN=$'\033[32m'; YEL=$'\033[33m'; RST=$'\033[0m'
else
    BOLD=""; RED=""; GRN=""; YEL=""; RST=""
fi
ok()   { printf '%s✓%s %s\n'  "$GRN" "$RST" "$*"; }
warn() { printf '%s!%s %s\n'  "$YEL" "$RST" "$*"; }
err()  { printf '%s✗%s %s\n'  "$RED" "$RST" "$*" >&2; }
hdr()  { printf '\n%s%s%s\n'  "$BOLD" "$*" "$RST"; }

# Build the list of candidate interpreters to probe. Order matters: explicit
# override first, then specific minor versions newest-first, then the generic
# python3. Probing newest-first means an upgraded OS is picked up automatically.
candidate_interpreters() {
    local c seen=" "
    local -a list=()

    if [ -n "${PYTHON_CANDIDATES:-}" ]; then
        # Intentional word-splitting of the space-separated override.
        # shellcheck disable=SC2206
        list=($PYTHON_CANDIDATES)
    else
        # Specific minor versions in /usr/bin, newest first (nullglob so an
        # unmatched glob expands to nothing rather than a literal).
        local restore_nullglob=1
        shopt -q nullglob || restore_nullglob=0
        shopt -s nullglob
        local -a versioned=(/usr/bin/python3.*)
        [ "$restore_nullglob" -eq 1 ] || shopt -u nullglob
        if [ "${#versioned[@]}" -gt 0 ]; then
            while IFS= read -r c; do list+=("$c"); done \
                < <(printf '%s\n' "${versioned[@]}" | sort -V -r)
        fi
        list+=("$(command -v python3 || true)")
    fi

    for c in "${list[@]}"; do
        [ -n "$c" ] || continue
        # Resolve to an absolute interpreter path; de-duplicate.
        c="$(command -v "$c" 2>/dev/null || echo "$c")"
        case "$seen" in *" $c "*) continue;; esac
        seen="$seen$c "
        printf '%s\n' "$c"
    done
}

# Probe: does this interpreter successfully import qgis.core?
# This single check validates BOTH that PyQt6 is visible to that interpreter AND
# that the interpreter's ABI matches QGIS's compiled _core.so — the two things
# that have to line up for notebooks to work.
probe_interpreter() {
    local py="$1"
    [ -x "$py" ] || return 1
    QT_QPA_PLATFORM=offscreen "$py" - "$QGIS_PYTHON_PATH" <<'PY' 2>/dev/null
import sys
sys.path.insert(0, sys.argv[1])
import qgis.core  # noqa: F401 — import is the test
print("%d.%d.%d" % sys.version_info[:3])
PY
}

# Detect QGIS's Python interpreter. Echoes "<path>\t<version>" on success.
detect_qgis_python() {
    local py ver
    while IFS= read -r py; do
        [ -n "$py" ] || continue
        if ver="$(probe_interpreter "$py")"; then
            printf '%s\t%s\n' "$py" "$ver"
            return 0
        fi
    done < <(candidate_interpreters)
    return 1
}

cmd_path() {
    local found
    if found="$(detect_qgis_python)"; then
        printf '%s\n' "${found%%$'\t'*}"
    else
        err "No interpreter could import qgis.core. Run './qgis-env.sh doctor'."
        return 1
    fi
}

cmd_doctor() {
    local fail=0

    hdr "QGIS bindings"
    if [ -d "$QGIS_PYTHON_PATH" ]; then
        ok "PyQGIS path exists: $QGIS_PYTHON_PATH"
    else
        err "PyQGIS path not found: $QGIS_PYTHON_PATH"
        warn "Set QGIS_PYTHON_PATH to your install's python dir, or install QGIS."
        fail=1
    fi

    hdr "Interpreter detection"
    local found py ver
    if found="$(detect_qgis_python)"; then
        py="${found%%$'\t'*}"; ver="${found##*$'\t'}"
        ok "QGIS loads under: $py (Python $ver)"
    else
        err "No system interpreter could import qgis.core."
        printf '  Interpreters probed (none worked):\n'
        local c
        while IFS= read -r c; do
            [ -n "$c" ] || continue
            local has_pyqt6="no"
            "$c" -c "import PyQt6" 2>/dev/null && has_pyqt6="yes"
            printf '    - %-22s PyQt6 importable: %s\n' "$c" "$has_pyqt6"
        done < <(candidate_interpreters)
        printf '\n  %sLikely fixes:%s\n' "$BOLD" "$RST"
        printf '    • Install the PyQt6 bindings for the interpreter QGIS uses, e.g.\n'
        printf '        Debian/Ubuntu: sudo apt install python3-pyqt6\n'
        printf '        Fedora:        sudo dnf install python3-pyqt6\n'
        printf '        Arch:          sudo pacman -S python-pyqt6\n'
        printf '    • Ensure the venv Python MATCHES QGIS (its _core.so is ABI-locked\n'
        printf '      to one Python minor version). Do not pin a different version.\n'
        fail=1
    fi

    hdr "Project venv"
    if [ -f "${VENV_DIR}/pyvenv.cfg" ]; then
        local venv_ver venv_sys
        venv_ver="$(grep -E '^version_info' "${VENV_DIR}/pyvenv.cfg" | cut -d= -f2 | tr -d ' ')"
        venv_sys="$(grep -E '^include-system-site-packages' "${VENV_DIR}/pyvenv.cfg" | cut -d= -f2 | tr -d ' ')"
        printf '  .venv Python:               %s\n' "${venv_ver:-unknown}"
        printf '  include-system-site-packages: %s\n' "${venv_sys:-unknown}"

        if [ "$venv_sys" != "true" ]; then
            err "venv lacks --system-site-packages; it cannot see system PyQt6."
            warn "Run './qgis-env.sh setup' to recreate it correctly."
            fail=1
        fi
        if [ -n "${ver:-}" ] && [ -n "$venv_ver" ] && [ "${venv_ver%.*}" != "${ver%.*}" ]; then
            err "venv Python ($venv_ver) != QGIS Python ($ver) — minor versions differ."
            warn "Run './qgis-env.sh setup' to rebuild against QGIS's interpreter."
            fail=1
        fi
        # End-to-end check: can the venv itself import qgis.core?
        if [ -x "${VENV_DIR}/bin/python" ] \
           && QT_QPA_PLATFORM=offscreen "${VENV_DIR}/bin/python" -c \
                "import sys; sys.path.insert(0,'$QGIS_PYTHON_PATH'); import qgis.core" 2>/dev/null; then
            ok "venv imports qgis.core successfully."
        else
            err "venv cannot import qgis.core."
            warn "Run './qgis-env.sh setup' to rebuild it."
            fail=1
        fi
    else
        warn "No .venv yet. Run './qgis-env.sh setup' to create it."
    fi

    hdr "Result"
    if [ "$fail" -eq 0 ]; then
        ok "Environment looks healthy."
    else
        err "Issues found — see fixes above."
        return 1
    fi
}

cmd_setup() {
    command -v uv >/dev/null 2>&1 || { err "uv not found on PATH. Install uv first."; return 1; }

    hdr "Detecting QGIS's Python"
    local found py ver
    if ! found="$(detect_qgis_python)"; then
        err "Could not find an interpreter that imports qgis.core."
        warn "Run './qgis-env.sh doctor' for a detailed diagnosis."
        return 1
    fi
    py="${found%%$'\t'*}"; ver="${found##*$'\t'}"
    ok "Using $py (Python $ver) — matches QGIS's bindings."

    hdr "Creating venv (system-site-packages, no version pin)"
    uv venv --python "$py" --system-site-packages --clear "$VENV_DIR"

    hdr "Installing notebook dependencies"
    # shellcheck disable=SC2086
    VIRTUAL_ENV="$VENV_DIR" uv pip install $MARIMO_DEPS

    hdr "Verifying"
    if QT_QPA_PLATFORM=offscreen "${VENV_DIR}/bin/python" -c \
        "import sys; sys.path.insert(0,'$QGIS_PYTHON_PATH'); from qgis.core import Qgis; print('QGIS', Qgis.version())"; then
        ok "Setup complete. Run notebooks with:  uv run marimo edit qgis_test.py"
    else
        err "Verification failed — the venv could not import QGIS."
        return 1
    fi
}

usage() {
    sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

main() {
    case "${1:-}" in
        doctor) cmd_doctor ;;
        setup)  cmd_setup ;;
        path)   cmd_path ;;
        -h|--help|help|"") usage ;;
        *) err "Unknown command: $1"; echo; usage; return 2 ;;
    esac
}

main "$@"
