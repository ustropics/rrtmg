#!/usr/bin/env python3
"""
generate_input_rrtm.py

Reads an RRTMG LW configuration from a JSON file and writes a properly
formatted INPUT_RRTM file.  Column positions follow the format spec in
rrtmg_lw_instructions.txt exactly.

Usage:
    python generate_input_rrtm.py                          # defaults
    python generate_input_rrtm.py -c my_config.json        # custom config
    python generate_input_rrtm.py -c cfg.json -o INPUT_RRTM  # custom output
"""

import json
import argparse
import sys


def load_config(path: str) -> dict:
    """Load JSON configuration, stripping comment keys."""
    with open(path) as f:
        raw = json.load(f)

    def strip_comments(obj):
        if isinstance(obj, dict):
            return {k: strip_comments(v) for k, v in obj.items()
                    if not k.startswith("_") and not k.endswith("_options")
                    and not k.endswith("_note")}
        return obj

    return strip_comments(raw)


# ── Fortran fixed-format helpers ──────────────────────────────────────────────

def place_str(line: list, col1: int, text: str):
    """Place a string starting at 1-based column col1."""
    idx = col1 - 1
    for i, ch in enumerate(text):
        line[idx + i] = ch


def fmt_int(value: int, width: int) -> str:
    """Right-justified integer in `width` characters (Fortran I format)."""
    return f"{value:{width}d}"


def fmt_float_e(value: float, width: int, decimals: int) -> str:
    """Fortran E format: e.g. E10.3 -> width 10, decimals 3."""
    return f"{value:{width}.{decimals}E}" if value != 0 else f"{value:{width}.{decimals}f}"


def fmt_float_f(value: float, width: int, decimals: int) -> str:
    """Fortran F format: e.g. F10.3 -> width 10, decimals 3."""
    return f"{value:{width}.{decimals}f}"


def make_line(length: int = 95) -> list:
    """Create a blank line of `length` spaces."""
    return [' '] * length


def line_to_str(line: list) -> str:
    return ''.join(line).rstrip()


# ── Record builders ───────────────────────────────────────────────────────────

def build_record_1_1(cfg: dict) -> list[str]:
    """RECORD 1.1 - Header and $ control line."""
    r = cfg["record_1_1"]
    return [r["header"], r["control_line"]]


def build_record_1_2(cfg: dict) -> str:
    """
    RECORD 1.2 - Main control flags.
    Format: 18X,I2, 29X,I1, 19X,I1, 13X,I2, 2X,I3, 1X,I1, 1X,I1, I1
    Columns:  20,     50,     70,   84-85, 88-90,  92,   94,  95
    """
    r = cfg["record_1_2"]
    line = make_line(95)

    # IAER at col 19-20 (I2)
    place_str(line, 19, fmt_int(r["IAER"], 2))
    # IATM at col 50 (I1)
    place_str(line, 50, fmt_int(r["IATM"], 1))
    # IXSECT at col 70 (I1)
    place_str(line, 70, fmt_int(r["IXSECT"], 1))
    # NUMANGS at col 84-85 (I2)
    place_str(line, 84, fmt_int(r["NUMANGS"], 2))
    # IOUT at col 88-90 (I3)
    place_str(line, 88, fmt_int(r["IOUT"], 3))
    # IDRV at col 92 (I1)
    place_str(line, 92, fmt_int(r["IDRV"], 1))
    # IMCA at col 94 (I1)
    place_str(line, 94, fmt_int(r["IMCA"], 1))
    # ICLD at col 95 (I1)
    place_str(line, 95, fmt_int(r["ICLD"], 1))

    return line_to_str(line)


def build_record_1_4(cfg: dict) -> str:
    """
    RECORD 1.4 - Surface properties.
    Format: E10.3, 1X,I1, 2X,I1, 16E5.3
    Columns: 1-10,  12,   15,    16-95
    """
    r = cfg["record_1_4"]
    line = make_line(95)

    # TBOUND at col 1-10 (E10.3) - format like original
    tbound_str = f"{r['TBOUND']:.1f}"
    place_str(line, 1, tbound_str)
    # IEMIS at col 12 (I1)
    place_str(line, 12, fmt_int(r["IEMIS"], 1))
    # IREFLECT at col 15 (I1)
    place_str(line, 15, fmt_int(r["IREFLECT"], 1))
    # SEMISS values starting at col 16, each 5 chars wide (E5.3)
    semiss = r.get("SEMISS", [])
    for i, val in enumerate(semiss):
        col = 16 + i * 5
        place_str(line, col, f"{val:5.2f}")

    return line_to_str(line)


def build_record_3_1(cfg: dict) -> str:
    """
    RECORD 3.1 - Atmospheric profile selection (IATM=1).
    Format: I5, 5X,I5, 5X,I5, I5, I5, 3X,I2, F10.3, 20X,F10.3
    Columns: 5,   15,   25,  30, 35, 39-40, 41-50, 71-80
    """
    r = cfg["record_3_1"]
    line = make_line(80)

    # MODEL at col 1-5 (I5)
    place_str(line, 1, fmt_int(r["MODEL"], 5))
    # IBMAX at col 11-15 (I5)
    place_str(line, 11, fmt_int(r["IBMAX"], 5))
    # NOPRNT at col 21-25 (I5)
    place_str(line, 21, fmt_int(r["NOPRNT"], 5))
    # NMOL at col 26-30 (I5)
    place_str(line, 26, fmt_int(r["NMOL"], 5))
    # IPUNCH at col 31-35 (I5)
    place_str(line, 31, fmt_int(r["IPUNCH"], 5))
    # MUNITS at col 39-40 (I2)
    place_str(line, 39, fmt_int(r["MUNITS"], 2))
    # RE at col 41-50 (F10.3) - write as simple int if zero
    re_val = r.get("RE", 0)
    if re_val != 0:
        place_str(line, 41, fmt_float_f(re_val, 10, 3))
    else:
        place_str(line, 45, "0")
    # CO2MX at col 71-80 (F10.3) - only write if nonzero
    if r.get("CO2MX", 0) != 0:
        place_str(line, 71, fmt_float_f(r["CO2MX"], 10, 3))
    else:
        # Match original: just a '0' at col 71
        place_str(line, 71, "0")

    return line_to_str(line)


def build_record_3_2(cfg: dict) -> str:
    """
    RECORD 3.2 - Altitude boundaries.
    Format: F10.3, F10.3
    Columns: 1-10, 11-20
    """
    r = cfg["record_3_2"]
    line = make_line(20)
    place_str(line, 1, f"{r['HBOUND']:.1f}")
    # HTOA at col 11-20 (F10.3)
    place_str(line, 11, fmt_float_f(r["HTOA"], 10, 1))
    return line_to_str(line)


def build_record_3_3a(cfg: dict) -> str:
    """
    RECORD 3.3A - Layer generation parameters (IBMAX=0).
    Format: F10.3, F10.3, F10.3, F10.3, F10.3
    Columns: 1-10, 11-20, 21-30, 31-40, 41-50
    """
    r = cfg["record_3_3a"]
    line = make_line(50)
    for i, key in enumerate(["AVTRAT", "TDIFF1", "TDIFF2", "ALTD1", "ALTD2"]):
        val = r.get(key, 0)
        col = 1 + i * 10
        place_str(line, col, fmt_float_f(float(val), 10, 0))
    return line_to_str(line)


def generate_input_rrtm(cfg: dict) -> str:
    """Assemble all records into a complete INPUT_RRTM file."""
    lines = []

    # Record 1.1 - header lines
    lines.extend(build_record_1_1(cfg))

    # Record 1.2 - control flags
    lines.append(build_record_1_2(cfg))

    # Record 1.4 - surface properties
    lines.append(build_record_1_4(cfg))

    iatm = cfg["record_1_2"]["IATM"]

    if iatm == 1:
        # Record 3.1 - atmospheric profile
        lines.append(build_record_3_1(cfg))

        # Record 3.2 - altitude boundaries
        lines.append(build_record_3_2(cfg))

        ibmax = cfg["record_3_1"].get("IBMAX", 0)
        if ibmax == 0:
            # Record 3.3A - layer generation params
            lines.append(build_record_3_3a(cfg))

    # Trailing blank line (end of input)
    lines.append("")

    return '\n'.join(lines) + '\n'


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate RRTMG LW INPUT_RRTM from a JSON configuration."
    )
    parser.add_argument(
        "-c", "--config",
        default="rrtmg_config.json",
        help="Path to JSON config file (default: rrtmg_config.json)"
    )
    parser.add_argument(
        "-o", "--output",
        default="INPUT_RRTM",
        help="Output filename (default: INPUT_RRTM)"
    )
    args = parser.parse_args()

    try:
        cfg = load_config(args.config)
    except FileNotFoundError:
        print(f"Error: Config file '{args.config}' not found.", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in '{args.config}': {e}", file=sys.stderr)
        sys.exit(1)

    content = generate_input_rrtm(cfg)

    with open(args.output, 'w') as f:
        f.write(content)

    print(f"Generated '{args.output}' from '{args.config}'")
    print(f"  MODEL = {cfg['record_3_1']['MODEL']} "
          f"({'tropical' if cfg['record_3_1']['MODEL'] == 1 else 'see docs'})")
    print(f"  TBOUND = {cfg['record_1_4']['TBOUND']} K")
    print(f"  IOUT = {cfg['record_1_2']['IOUT']}")


if __name__ == "__main__":
    main()