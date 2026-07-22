#!/usr/bin/env python3
"""
INCAR에 MAGMOM 줄을 넣거나 갱신한다.
  - 기본: POSCAR + 원소별 magmom_values (n*값 형식)
  - --outcar: OUTCAR의 'magnetization (x)' 블록에서 이온별 tot (스트리밍 파싱)
  - --step: 사용할 블록 번호 (양수=파일 앞에서 n번째, 음수=끝에서 n번째, -1=마지막)
  - --outcar -5 처럼 정수만 주면 경로는 OUTCAR, step=-5 로 해석
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

MARKER = "magnetization (x)"
# --outcar -5 처럼 '경로' 자리에 온 순수 정수(부호 포함)는 OUTCAR+step으로 해석
_OUTCAR_INT_ONLY = re.compile(r"^-?\d+$")


def parse_magnetization_x_block(lines: list[str]) -> list[tuple[int, float, float, float, float, float]]:
    """블록 본문에서 (ion, s, p, d, tot) 리스트."""
    rows: list[tuple[int, float, float, float, float, float]] = []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("---"):
            continue
        if line.lower().startswith("tot"):
            break
        parts = line.split()
        if len(parts) < 5 or not parts[0].isdigit():
            continue
        ion = int(parts[0])
        s, p, d, tot = map(float, parts[1:5])
        rows.append((ion, s, p, d, tot))
    rows.sort(key=lambda t: t[0])
    return rows


def extract_all_magnetization_x_blocks(outcar_path: Path) -> list[list[tuple[int, float, float, float, float, float]]]:
    """
    OUTCAR 전체를 한 번 읽어, 등장 순서대로 완결된 magnetization (x) 블록마다
    (ion, s, p, d, tot) 행 리스트를 모은다. (대용량: 블록 단위로만 메모리 사용)
    """
    completed: list[list[tuple[int, float, float, float, float, float]]] = []
    block_buffer: list[str] = []
    collecting = False
    seen_header = False

    def flush_block() -> None:
        nonlocal block_buffer
        if not block_buffer:
            return
        rows = parse_magnetization_x_block(block_buffer)
        if rows:
            completed.append(rows)
        block_buffer = []

    with outcar_path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            if MARKER in line:
                block_buffer = []
                collecting = True
                seen_header = False
                continue

            if not collecting:
                continue

            stripped = line.strip()

            if "# of ion" in line and "tot" in line:
                seen_header = True
                continue
            if seen_header and stripped.startswith("---"):
                continue

            if seen_header:
                if stripped.lower().startswith("tot"):
                    flush_block()
                    collecting = False
                    continue
                if stripped and stripped[0].isdigit():
                    block_buffer.append(line)
                    continue
                if stripped and not stripped.startswith("---"):
                    collecting = False

    flush_block()

    if not completed:
        raise ValueError(
            f"'{MARKER}' 완결 블록을 찾지 못했거나 헤더 형식이 예상과 다릅니다: {outcar_path}"
        )

    return completed


def select_magnetization_block(
    blocks: list[list[tuple[int, float, float, float, float, float]]],
    step: int,
) -> list[tuple[int, float, float, float, float, float]]:
    """
    step > 0 : 파일에서 n번째 블록 (1-based)
    step <= 0 : 끝에서 |step|번째; -1이 마지막 (Python 음수 인덱스와 동일)
    """
    n = len(blocks)
    if step == 0:
        raise ValueError("step은 0일 수 없습니다. 양수(앞에서) 또는 음수(끝에서)를 사용하세요.")
    if step > 0:
        if step > n:
            raise ValueError(f"step={step} 은 범위를 벗어났습니다 (magnetization (x) 블록은 총 {n}개).")
        return blocks[step - 1]
    idx = step  # -1 -> 마지막
    if -step > n:
        raise ValueError(
            f"step={step} 은 범위를 벗어났습니다 (끝에서 최대 {n}번째까지, 블록 총 {n}개)."
        )
    return blocks[idx]


def format_magmom_line(values: list[float], decimals: int | None) -> str:
    if decimals is None:
        return "  ".join(f"{v}" for v in values)
    fmt = f"{{:.{decimals}f}}"
    return "  ".join(fmt.format(v) for v in values)


def generate_magmom_from_outcar(
    outcar_path: Path,
    decimals: int | None = None,
    step: int = -1,
) -> tuple[str, int, int]:
    """
    OUTCAR에서 지정 step의 magnetization (x) 이온별 tot → MAGMOM 한 줄.
    반환: (magmom_line, block_index_1based_from_start, total_blocks)
    """
    blocks = extract_all_magnetization_x_blocks(outcar_path)
    n = len(blocks)
    rows = select_magnetization_block(blocks, step)
    mags = [r[4] for r in rows]  # (ion, s, p, d, tot)
    body = format_magmom_line(mags, decimals)
    line = " MAGMOM = " + body
    pos_1based = step if step > 0 else n + step + 1
    return line, pos_1based, n


def generate_magmom_from_poscar(poscar_path):
    with open(poscar_path, 'r') as f:
        lines = f.readlines()

    elements = lines[5].split()                     # 6번째 줄: 원소 기호
    counts = list(map(int, lines[6].split()))       # 7번째 줄: 각 원소 개수

    # 원소별 MAGMOM 값 매핑 (Materials Project 데이터 기반)
    # 0이 아닌 값들만 명시, 나머지는 자동으로 0.0으로 설정됨
    magmom_values = {
        # 3d 전이금속
        'Sc': 1.0,  # 스칸듐
        'Mn': 5.0,  # 망간
        'Fe': 3.0,  # 철
        'Co': 2.0,  # 코발트
        'Ni': 1.0,  # 니켈
        # HEA 전용 
       # 'Cu': 1.0,  # 구리 
       # 'Cr': 1.0,  # 알루미늄 


        # 4d 전이금속
        'Y': 1.0,   # 이트륨
        'Pd': 1.0,  # 팔라듐
        
        # 란타넘족
        'Eu': 9.0,  # 유로퓸
        'Gd': 8.0,  # 가돌리늄
        'Yb': 1.0,  # 이터븀
        'Lu': 1.0,  # 루테튬
        
        # 악티늄족
        'Pu': 3.0   # 플루토늄
    }
    
    magmom_list = []
    print("원소별 MAGMOM 값 설정:")
    for elem, count in zip(elements, counts):
        magmom_value = magmom_values.get(elem, 0.0)  # 기본값은 0.0
        magmom_list.append(f"{count}*{magmom_value}")
        print(f"  {elem}: {count}개 원자 × {magmom_value} = {count}*{magmom_value}")

    magmom_string = ' MAGMOM = ' + ' '.join(magmom_list)
    print(f"생성된 MAGMOM 문자열: {magmom_string}")
    return magmom_string

def insert_magmom_into_incar(incar_path, magmom_line):
    with open(incar_path, 'r') as f:
        incar_lines = f.readlines()

    new_incar_lines = []
    magmom_inserted = False

    for line in incar_lines:
        stripped = line.strip()
        if stripped.startswith("MAGMOM") and not stripped.startswith("#"):
            if not magmom_inserted:
                new_incar_lines.append(magmom_line + '\n')
                magmom_inserted = True
            continue
        new_incar_lines.append(line)

    if not magmom_inserted:
        new_incar_lines.append(magmom_line + '\n')

    with open(incar_path, 'w') as f:
        f.writelines(new_incar_lines)

    print("MAGMOM 줄이 INCAR에 성공적으로 추가되었습니다.")

# 실행 진입점
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="INCAR에 MAGMOM 줄 삽입/갱신 (기본: POSCAR+원소별 magmom_values, 선택: OUTCAR)"
    )
    parser.add_argument(
        "poscar",
        nargs="?",
        default="POSCAR",
        help="POSCAR 경로 (--outcar 미사용 시 필수로 존재해야 함, 기본: POSCAR)",
    )
    parser.add_argument(
        "--outcar",
        nargs="?",
        const="OUTCAR",
        default=None,
        type=str,
        metavar="PATH_OR_STEP",
        help="OUTCAR에서 magnetization(x) 이온별 MAGMOM. "
        "인자 생략 시 ./OUTCAR. "
        "인자가 순수 정수(예: -5)이고 그 이름의 파일이 없으면 "
        "경로는 OUTCAR, step으로 해석 (끝에서 5번째 블록).",
    )
    parser.add_argument(
        "--step",
        type=int,
        default=None,
        help="블록 선택: 양수=앞에서 n번째(1부터), 음수=끝에서 n번째(-1=마지막). "
        "미지정이면 --outcar가 정수 형태일 때만 그 값을 step으로 쓰고, 아니면 -1(마지막).",
    )
    parser.add_argument(
        "--decimals",
        type=int,
        default=None,
        help="--outcar 사용 시 소수 자릿수 (미지정이면 추출값 그대로)",
    )
    args = parser.parse_args()

    incar_path = "INCAR"
    if not os.path.isfile(incar_path):
        print("에러: INCAR 파일이 존재하지 않습니다. 새로 만들지 않습니다.")
        sys.exit(1)

    if args.outcar is not None:
        raw = args.outcar.strip()
        step_val: int
        if args.step is not None:
            outcar_path = Path(raw)
            step_val = args.step
        elif _OUTCAR_INT_ONLY.match(raw) and not Path(raw).is_file():
            outcar_path = Path("OUTCAR")
            step_val = int(raw)
        else:
            outcar_path = Path(raw)
            step_val = -1

        if not outcar_path.is_file():
            print(f"에러: OUTCAR를 찾을 수 없습니다: {outcar_path}")
            sys.exit(1)

        print(f"OUTCAR에서 MAGMOM 추출: {outcar_path.resolve()} (step={step_val})")
        magmom_line, pos_1based, n_blocks = generate_magmom_from_outcar(
            outcar_path, decimals=args.decimals, step=step_val
        )
        print(f"선택된 블록: 앞에서 {pos_1based}번째 / 총 {n_blocks}개 magnetization (x)")
        print(f"생성된 MAGMOM 문자열:{magmom_line}")
    else:
        poscar_path = args.poscar
        if not os.path.isfile(poscar_path):
            print("에러: POSCAR 파일이 없습니다 (--outcar 없이는 POSCAR가 필요합니다).")
            print("사용법: python magmom_incar [POSCAR]  |  python magmom_incar --outcar [OUTCAR]")
            sys.exit(1)
        magmom_line = generate_magmom_from_poscar(poscar_path)

    insert_magmom_into_incar(incar_path, magmom_line)

"""
사용법:
========

1. 기본 사용 (POSCAR 파일이 현재 디렉토리에 있는 경우):
   ./magmom_incar

2. 특정 POSCAR 파일 지정:
   ./magmom_incar my_poscar_file

3. OUTCAR에서 magnetization (x) 이온별 tot으로 MAGMOM 설정:
   ./magmom_incar --outcar
   ./magmom_incar --outcar path/to/OUTCAR
   ./magmom_incar --outcar OUTCAR --decimals 3
   ./magmom_incar --outcar -5          # ./OUTCAR, 끝에서 5번째 블록 (마지막이 -1)
   ./magmom_incar --outcar ./OUTCAR --step 10   # 10번째 블록(파일 앞에서)
   ./magmom_incar --outcar ./OUTCAR --step -2   # 끝에서 2번째 (= 마지막 직전)

4. Python으로 직접 실행:
   python3 magmom_incar [POSCAR]
   python3 magmom_incar --outcar [OUTCAR]

기능:
======
- POSCAR 파일에서 원소 정보를 읽어와서 자동으로 MAGMOM 값을 설정
- Materials Project 데이터 기반의 원소별 자성 모멘트 값 사용
- INCAR 파일에 MAGMOM 라인을 자동으로 추가/수정

지원하는 자성 원소:
==================
3d 전이금속: Sc(1.0), Mn(1.0), Fe(3.0), Co(2.0), Ni(1.0)
4d 전이금속: Y(1.0), Pd(1.0)
란타넘족: Eu(9.0), Gd(8.0), Yb(1.0), Lu(1.0)
악티늄족: Pu(3.0)
기타 모든 원소: 0.0 (비자성)

예시:
=====
POSCAR에 Fe 2개, Co 1개, C 1개가 있다면:
MAGMOM = 2*3.0 1*2.0 1*0.0

주의사항:
=========
- INCAR 파일이 현재 디렉토리에 존재해야 함
- POSCAR 파일 형식이 VASP 표준을 따라야 함
- 기존 MAGMOM 라인이 있으면 자동으로 교체됨
"""

