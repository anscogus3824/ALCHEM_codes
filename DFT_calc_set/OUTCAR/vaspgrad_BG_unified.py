#!/usr/bin/python3

# *****************************************************************************
#   vaspgrad_BG_unified.py
#   CPU/GPU VASP OUTCAR 모두 지원하는 통합 버전
#   원본: vaspgrad3.0.py by Peter Larsson (2008-2012)
#
#   변경사항:
#   - GPU 버전 VASP OUTCAR 지원 추가 (FORCES: max atom 줄 없는 경우)
#   - TOTAL-FORCE 섹션에서 직접 max/avg force 계산
#   - 파일 스캔으로 CPU/GPU 모드 자동 감지
# *****************************************************************************

import subprocess
import os
import sys
import math
import re
import argparse
import platform

def getoutput(command):
    try:
        if hasattr(subprocess, 'getoutput'):
            return subprocess.getoutput(command)
        elif hasattr(subprocess, 'run'):
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            return result.stdout.strip()
        else:
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            stdout, stderr = process.communicate()
            return stdout.strip()
    except Exception:
        return ""

def get_number_of_atoms(outcar_file):
    try:
        output = getoutput("grep -ah \"NIONS\" {}".format(outcar_file))
        if output:
            parts = output.split()
            for i, part in enumerate(parts):
                if part == '=' and i + 1 < len(parts):
                    try:
                        return int(parts[i + 1])
                    except ValueError:
                        continue
                if 'NIONS' in part and '=' in part:
                    value = part.split('=')[1]
                    if value.isdigit():
                        return int(value)
            if len(parts) > 11:
                return int(parts[11])
            raise ValueError("Could not parse NIONS from: {}".format(output))
        else:
            raise ValueError("NIONS not found in OUTCAR")
    except (IndexError, ValueError) as e:
        print("Error extracting number of atoms: {}".format(e))
        return 0

def get_ediff(outcar_file):
    try:
        output = getoutput("grep -ah \"  EDIFF\" {}".format(outcar_file))
        if output:
            parts = output.split()
            for i, part in enumerate(parts):
                if part == '=' and i + 1 < len(parts):
                    try:
                        return float(parts[i + 1])
                    except ValueError:
                        continue
                if 'EDIFF' in part and '=' in part:
                    value = part.split('=')[1]
                    try:
                        return float(value)
                    except ValueError:
                        continue
            if len(parts) > 2:
                return float(parts[2])
            raise ValueError("Could not parse EDIFF from: {}".format(output))
        else:
            raise ValueError("EDIFF not found in OUTCAR")
    except (IndexError, ValueError) as e:
        print("Error extracting EDIFF: {}".format(e))
        return 1e-4

def get_nelmax(outcar_file):
    try:
        output = getoutput("grep -ah \"NELM.*# of ELM steps\" {}".format(outcar_file))
        if not output:
            output = getoutput("grep -ah \"NELM\" {}".format(outcar_file))
        if output:
            lines = output.split('\n')
            for line in lines:
                if 'NELM' not in line:
                    continue
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == '=' and i + 1 < len(parts):
                        try:
                            value = parts[i + 1].rstrip(';')
                            return int(value)
                        except ValueError:
                            continue
                    if 'NELM' in part and '=' in part:
                        value = part.split('=')[1].rstrip(';')
                        try:
                            return int(value)
                        except ValueError:
                            continue
                if len(parts) > 2:
                    try:
                        for j, part in enumerate(parts):
                            if 'NELM' in part and j + 2 < len(parts):
                                if parts[j+1] == '=':
                                    value = parts[j+2].rstrip(';')
                                    return int(value)
                    except (ValueError, IndexError):
                        pass
            raise ValueError("Could not parse NELM from: {}".format(output))
        else:
            raise ValueError("NELM not found in OUTCAR")
    except (IndexError, ValueError) as e:
        print("Error extracting NELM: {}".format(e))
        return 500

def get_colors():
    try:
        if os.environ.get('NO_COLOR'):
            return {'OKGREEN': '', 'WARNING': '', 'FAIL': '', 'ENDC': ''}
        if hasattr(sys.stdout, 'isatty') and sys.stdout.isatty():
            return {
                'OKGREEN': '\033[92m',
                'WARNING': '\033[93m',
                'FAIL': '\033[91m',
                'ENDC': '\033[0m'
            }
        else:
            return {'OKGREEN': '', 'WARNING': '', 'FAIL': '', 'ENDC': ''}
    except Exception:
        return {'OKGREEN': '', 'WARNING': '', 'FAIL': '', 'ENDC': ''}

def safe_float(s):
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0

def process_forces_from_block(outcarlines, i):
    """TOTAL-FORCE 블록에서 직접 max/avg force 계산"""
    forces = []
    j = i + 2  # 헤더 2줄 건너뜀
    while j < len(outcarlines):
        fline = outcarlines[j]
        if "---" in fline or "total drift" in fline:
            break
        fparts = fline.split()
        if len(fparts) == 6:
            try:
                fx, fy, fz = float(fparts[3]), float(fparts[4]), float(fparts[5])
                forces.append(math.sqrt(fx**2 + fy**2 + fz**2))
            except ValueError:
                pass
        j += 1
    if forces:
        return sum(forces) / len(forces), max(forces)
    return 0.0, 0.0

def print_header():
    print("")
    print("=" * 100)
    print("VASP Calculation Summary (vaspgrad_BG_unified)")
    print("=" * 100)
    print("Step  Energy         Log|dE|    SCF  Avg|F|   Max|F|   Vol.    Mag.   Time")
    print("-" * 100)

def print_summary(totaltime, outcar_file, colors):
    print("-" * 100)
    try:
        th, tm = divmod(totaltime, 60)
        print("Total CPU time: {} hour, {:02d} min.".format(int(th), int(tm)))
        elapsed_output = getoutput("grep -ah \"Elapsed time (sec):\" {}".format(outcar_file))
        if elapsed_output:
            elapsedt = safe_float(elapsed_output.split()[-1])
            m, s = divmod(elapsedt, 60)
            h, m = divmod(m, 60)
            print("Elapsed time (h:m:s): {}:{:02d}:{:02d}".format(int(h), int(m), int(s)))
        else:
            print("Elapsed time not found in OUTCAR")
    except Exception as e:
        print("Error calculating timing summary: {}".format(e))

def read_nsw_from_incar(incar_path="INCAR"):
    try:
        with open(incar_path, "r") as f:
            for line in f:
                match = re.match(r"\s*NSW\s*=\s*(\d+)", line)
                if match:
                    return int(match.group(1))
    except Exception:
        pass
    return 100

def main():
    parser = argparse.ArgumentParser(
        description='VASP calculation summary tool - CPU/GPU unified version',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python vaspgrad_BG_unified.py OUTCAR
  python vaspgrad_BG_unified.py -v OUTCAR
        """
    )
    parser.add_argument('outcar_file', help='OUTCAR file to analyze')
    parser.add_argument('-v', '--verbose', action='store_true', help='Print extra debug info')
    parser.add_argument('--force-colors', action='store_true', help='Force color output')
    parser.add_argument('--version', action='version', version='vaspgrad_BG_unified')
    args = parser.parse_args()

    colors = get_colors()
    if args.force_colors:
        colors = {
            'OKGREEN': '\033[92m',
            'WARNING': '\033[93m',
            'FAIL': '\033[91m',
            'ENDC': '\033[0m'
        }

    nsw = read_nsw_from_incar()
    if args.verbose:
        print("NSW from INCAR: {}".format(nsw))

    if not os.path.exists(args.outcar_file):
        sys.stderr.write("{}Error: File '{}' not found{}\n".format(colors['FAIL'], args.outcar_file, colors['ENDC']))
        sys.exit(1)

    try:
        with open(args.outcar_file, "r") as outcar:
            outcarlines = outcar.readlines()
    except IOError as e:
        sys.stderr.write("{}Error opening file '{}': {}{}\n".format(colors['FAIL'], args.outcar_file, e, colors['ENDC']))
        sys.exit(1)

    try:
        nelmax = get_nelmax(args.outcar_file)
        natoms = get_number_of_atoms(args.outcar_file)
        ediff = math.log10(float(get_ediff(args.outcar_file)))
        if natoms == 0:
            sys.stderr.write("{}Error: Could not determine number of atoms{}\n".format(colors['FAIL'], colors['ENDC']))
            sys.exit(1)
        if args.verbose:
            print("Parameters: NELM={}, NIONS={}, EDIFF={:.2e}".format(nelmax, natoms, 10**ediff))
    except Exception as e:
        sys.stderr.write("{}Error reading OUTCAR parameters: {}{}\n".format(colors['FAIL'], e, colors['ENDC']))
        sys.exit(1)

    # -------------------------------------------------------
    # CPU/GPU 모드 자동 감지
    # CPU: OUTCAR에 "FORCES: max atom" 줄 존재
    # GPU: 해당 줄 없음 → TOTAL-FORCE 블록에서 직접 계산 후 free energy 줄에서 출력
    # -------------------------------------------------------
    gpu_mode = not any("FORCES: max atom" in l for l in outcarlines)
    if args.verbose:
        print("Mode: {}".format("GPU (OpenACC offload)" if gpu_mode else "CPU"))

    # Compile regex patterns
    re_energy        = re.compile("free  energy")
    re_iteration     = re.compile("Iteration")
    re_timing        = re.compile("LOOP:")
    re_totalforce    = re.compile("TOTAL-FORCE")
    re_forces_cpu    = re.compile("FORCES: max atom")
    re_mag           = re.compile("number of electron")
    re_volume        = re.compile("volume of cell")

    # Initialize variables
    lastenergy   = 0.0
    energy       = 0.0
    steps        = 1
    iterations   = 0
    cputime      = 0.0
    totaltime    = 0.0
    dE           = 0.0
    magmom       = 0.0
    spinpolarized = False
    volume       = 0.0
    average      = 0.0
    bkmaxforce   = 0.0

    print_header()

    for i, line in enumerate(outcarlines):

        if re_iteration.search(line):
            iterations += 1

        if re_mag.search(line):
            parts = line.split()
            if len(parts) > 5 and parts[0].strip() != "NELECT":
                spinpolarized = True
                magmom = safe_float(parts[5])

        if re_timing.search(line):
            parts = line.split()
            if len(parts) > 6:
                cputime += safe_float(parts[6]) / 60.0

        if re_volume.search(line):
            parts = line.split()
            if len(parts) > 4:
                volume = safe_float(parts[4])

        if re_energy.search(line):
            lastenergy = energy
            parts = line.split()
            if len(parts) > 4:
                energy = safe_float(parts[4])
                dE = math.log10(abs(energy - lastenergy + 1.0E-12))

        # TOTAL-FORCE 블록에서 force 계산 (CPU/GPU 공통)
        if re_totalforce.search(line):
            avg, maxf = process_forces_from_block(outcarlines, i)
            if maxf > 0.0:
                average = avg
                bkmaxforce = maxf

        # -------------------------------------------------------
        # 출력 트리거
        # CPU 모드: "FORCES: max atom" 줄에서 출력
        # GPU 모드: "free  energy" 줄에서 출력 (bkmaxforce가 계산된 경우)
        # -------------------------------------------------------
        trigger_output = False

        if not gpu_mode and re_forces_cpu.search(line):
            # CPU: FORCES: max atom, RMS  <max>  <rms>
            parts = line.split()
            if len(parts) >= 6:
                try:
                    bkmaxforce = float(parts[4])
                    average    = float(parts[5])
                except (ValueError, IndexError):
                    pass
            trigger_output = True

        elif gpu_mode and re_energy.search(line) and bkmaxforce > 0.0:
            trigger_output = True

        if trigger_output and energy != 0.0:
            try:
                stepstr   = str(steps).rjust(4)
                energystr = ("%3.6f" % energy).rjust(12)
                logdestr  = ("%1.3f" % dE).rjust(6)
                iterstr   = ("%3i" % iterations).rjust(3)
                avgfstr   = ("%2.3f" % average).rjust(6)
                maxfstr   = ("%2.3f" % bkmaxforce).rjust(6)
                timestr   = ("%3.2fm" % cputime).rjust(6)
                volstr    = ("%3.1f" % volume).rjust(6)
            except Exception as e:
                if args.verbose:
                    print("Cannot understand OUTCAR at line {}: {}".format(i, e))
                continue

            if iterations >= nelmax:
                sys.stdout.write(colors['FAIL'])
            elif iterations <= 10:
                sys.stdout.write(colors['OKGREEN'])

            if spinpolarized:
                magstr = ("%2.2f" % magmom).rjust(6)
                print("{}  {}  {}      {} {}   {}   {} {}  {}".format(
                    stepstr, energystr, logdestr, iterstr, avgfstr, maxfstr, volstr, magstr, timestr))
            else:
                print("{}  {}  {}      {} {}   {}   {}        {}".format(
                    stepstr, energystr, logdestr, iterstr, avgfstr, maxfstr, volstr, timestr))

            sys.stdout.write(colors['ENDC'])
            steps      += 1
            iterations  = 0
            totaltime  += cputime
            cputime     = 0.0
            bkmaxforce  = 0.0

    print_summary(totaltime, args.outcar_file, colors)

if __name__ == "__main__":
    main()
