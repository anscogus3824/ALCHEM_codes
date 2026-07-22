#! /home/bogeun1007/anaconda3/bin/python

"""Update the MAGMOM line in an INCAR from the final moments in OUTCAR."""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path


def read_magmoms_with_ase(outcar: Path) -> list[float]:
    from ase.io import read

    atoms = read(str(outcar), index=-1, format="vasp-out")
    magmoms = atoms.get_magnetic_moments()

    values: list[float] = []
    for moment in magmoms:
        if hasattr(moment, "__iter__"):
            values.extend(float(component) for component in moment)
        else:
            values.append(float(moment))
    return values


def read_magmoms_from_outcar(outcar: Path) -> list[float]:
    """Fallback parser for the last OUTCAR 'magnetization (x)' block."""

    lines = outcar.read_text(errors="ignore").splitlines()
    starts = [i for i, line in enumerate(lines) if "magnetization (x)" in line]
    if not starts:
        raise RuntimeError("Could not find a 'magnetization (x)' block in OUTCAR.")

    i = starts[-1]
    while i < len(lines) and not re.match(r"^\s*-+\s*$", lines[i]):
        i += 1
    i += 1

    magmoms: list[float] = []
    for line in lines[i:]:
        fields = line.split()
        if not fields:
            continue
        if fields[0].lower() == "tot":
            break
        if fields[0].isdigit():
            magmoms.append(float(fields[-1]))

    if not magmoms:
        raise RuntimeError("Found 'magnetization (x)', but no per-ion moments were parsed.")
    return magmoms


def read_magmoms(outcar: Path) -> list[float]:
    try:
        return read_magmoms_with_ase(outcar)
    except Exception as exc:
        print(f"ASE read failed ({exc}); falling back to direct OUTCAR parsing.")
        return read_magmoms_from_outcar(outcar)


def next_backup_path(path: Path) -> Path:
    candidate = path.with_name(path.name + ".bak")
    if not candidate.exists():
        return candidate

    for index in range(1, 1000):
        candidate = path.with_name(f"{path.name}.bak{index}")
        if not candidate.exists():
            return candidate

    raise RuntimeError(f"Too many backup files already exist for {path}.")


def split_inline_comment(line: str) -> tuple[str, str]:
    comment_positions = [pos for marker in ("!", "#") if (pos := line.find(marker)) != -1]
    if not comment_positions:
        return line.rstrip("\n"), ""

    comment_start = min(comment_positions)
    return line[:comment_start].rstrip(), line[comment_start:].rstrip("\n")


def format_magmom_line(values: list[float], decimals: int, zero_threshold: float) -> str:
    cleaned = [0.0 if abs(value) < zero_threshold else value for value in values]
    formatted = " ".join(f"{value:.{decimals}f}" for value in cleaned)
    return f"  MAGMOM = {formatted}"


def is_magmom_line(line: str) -> bool:
    stripped = line.lstrip()
    return bool(re.match(r"^(?:[#\!]\s*)?MAGMOM\b", stripped, flags=re.IGNORECASE))


def update_incar(incar: Path, magmom_line: str) -> bool:
    lines = incar.read_text().splitlines(keepends=True)
    updated = False

    for index, line in enumerate(lines):
        active_part, comment = split_inline_comment(line)
        if re.match(r"^\s*MAGMOM\b", active_part, flags=re.IGNORECASE):
            newline = "\n" if line.endswith("\n") else ""
            comment_suffix = f"  {comment}" if comment else ""
            lines[index] = f"{magmom_line}{comment_suffix}{newline}"
            updated = True
            break
        if is_magmom_line(line):
            newline = "\n" if line.endswith("\n") else ""
            lines[index] = f"{magmom_line}{newline}"
            updated = True
            break

    if not updated:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines.append(f"{magmom_line}\n")

    incar.write_text("".join(lines))
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read final magnetic moments from OUTCAR and update MAGMOM in INCAR."
    )
    parser.add_argument("--outcar", default="OUTCAR", help="Path to OUTCAR. Default: OUTCAR")
    parser.add_argument("--incar", default="INCAR", help="Path to INCAR. Default: INCAR")
    parser.add_argument("--decimals", type=int, default=4, help="Decimal places. Default: 4")
    parser.add_argument(
        "--zero-threshold",
        type=float,
        default=0.0,
        help="Set values with abs(moment) below this threshold to 0.0. Default: 0.0",
    )
    parser.add_argument("--backup", action="store_true", help="Create an INCAR backup before editing.")
    parser.add_argument("--dry-run", action="store_true", help="Print the new MAGMOM line only.")
    args = parser.parse_args()

    outcar = Path(args.outcar)
    incar = Path(args.incar)

    if not outcar.exists():
        raise FileNotFoundError(f"OUTCAR not found: {outcar}")
    if not incar.exists() and not args.dry_run:
        raise FileNotFoundError(f"INCAR not found: {incar}")

    magmoms = read_magmoms(outcar)
    magmom_line = format_magmom_line(magmoms, args.decimals, args.zero_threshold)

    if args.dry_run:
        print(magmom_line)
        return

    if args.backup:
        backup = next_backup_path(incar)
        shutil.copy2(incar, backup)
        print(f"Backup written: {backup}")

    replaced_existing_line = update_incar(incar, magmom_line)
    action = "Updated existing MAGMOM line" if replaced_existing_line else "Appended MAGMOM line"
    print(f"{action}: {incar}")
    print(magmom_line)


if __name__ == "__main__":
    main()
