#!/usr/bin/env python3
import argparse
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Mapping, Sequence, Set, Tuple


ChangeMap = Dict[str, str]
COMMENT_VALUE = "#"
DEFAULT_INCAR_PATH = "INCAR"


@dataclass(frozen=True)
class IncarPreset:
    """계산 목적별 INCAR 변경 묶음.

    changes에는 {"TAG": "VALUE"} 형태로 넣습니다.
    값을 "#"로 두면 해당 TAG 줄을 주석 처리합니다.
    """

    description: str
    changes: Mapping[str, str]


ONESHOT_CHANGES: ChangeMap = {
    "NSW": "0",
    "NELM": "1000",
    "LWAVE": "T",
    "LCHARG": "T",
}

DOS_CHANGES: ChangeMap = {
    "NSW": "0",
    "NELM": "1000",
    "LWAVE": "T",
    "LCHARG": "T",
    "ISMEAR": "-5",
    "SIGMA": "0.03",
    "ICHARG": "11",
    "LORBIT": "11",
    "NEDOS": "5001",
}

COHP_CHANGES: ChangeMap = {
    "NSW": "0",
    "NELM": "1000",
    "ISYM": "-1",
    "LWAVE": "T",
    "LCHARG": "T",
    "NBANDS": "1500",
}

ZPE_CHANGES: ChangeMap = {
    "NSW": "1",
    "NELM": "1000",
    "IBRION": "5",
    "NFREE": "2",
    "EDIFF": "1.0E-08",
    "POTIM": "0.015",
    "ISMEAR": "0",
    "SIGMA": "0.05",
    "NPAR": COMMENT_VALUE,
}


PRESETS: Dict[str, IncarPreset] = {
    "oneshot": IncarPreset(
        description="one-shot 계산용 INCAR 설정",
        changes=ONESHOT_CHANGES,
    ),
    "dos": IncarPreset(
        description="DOS 분석용 INCAR 설정",
        changes=DOS_CHANGES,
    ),
    "cohp": IncarPreset(
        description="COHP 분석용 INCAR 설정",
        changes=COHP_CHANGES,
    ),
    "zpe": IncarPreset(
        description="ZPE 계산용 INCAR 설정",
        changes=ZPE_CHANGES,
    ),
    "phonon": IncarPreset(
        description="ZPE/phonon 계산용 INCAR 설정 alias",
        changes=ZPE_CHANGES,
    ),
}


_TAG_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_TAG_LINE_RE = re.compile(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*=)(.*)$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "현재 디렉터리의 INCAR 파일에서 태그 값을 변경합니다. "
            "계산 목적별 preset은 PRESETS에 등록해서 확장할 수 있습니다."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "예시:\n"
            "  python incar_change.py ENCUT 520 ISMEAR -5\n"
            "  python incar_change.py LDAU '#'\n"
            "  python incar_change.py --preset dos\n"
            "  python incar_change.py --preset zpe\n"
            "  python incar_change.py --preset dos NEDOS 3000\n"
            "  python incar_change.py --list-presets"
        ),
    )
    parser.add_argument(
        "pairs",
        nargs="*",
        help="TAG VALUE 쌍을 순서대로 입력합니다. 예: ENCUT 520 ISMEAR -5",
    )
    parser.add_argument(
        "-f",
        "--file",
        default=DEFAULT_INCAR_PATH,
        help=f"수정할 INCAR 파일 경로입니다. 기본값: {DEFAULT_INCAR_PATH}",
    )
    parser.add_argument(
        "-p",
        "--preset",
        dest="presets",
        action="append",
        default=[],
        metavar="NAME",
        help=(
            "적용할 preset 이름입니다. 여러 번 지정하면 순서대로 합치며, "
            "나중 preset과 직접 입력한 TAG VALUE가 앞의 값을 덮어씁니다."
        ),
    )
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="사용 가능한 preset 목록을 출력합니다.",
    )
    return parser.parse_args()


def normalize_tag(tag: str) -> str:
    tag_upper = tag.upper()
    if not _TAG_NAME_RE.match(tag_upper):
        raise SystemExit(f"[오류] 올바르지 않은 TAG 이름입니다: {tag}")
    return tag_upper


def normalize_changes(changes: Mapping[str, str]) -> ChangeMap:
    return {normalize_tag(tag): str(value) for tag, value in changes.items()}


def build_change_map(pairs: Sequence[str]) -> ChangeMap:
    if len(pairs) % 2 != 0:
        raise SystemExit("[오류] TAG와 VALUE는 짝수 개로 입력해야 합니다. 예: ENCUT 520 ISMEAR -5")

    changes: ChangeMap = {}
    for idx in range(0, len(pairs), 2):
        tag = normalize_tag(pairs[idx])
        value = pairs[idx + 1]
        changes[tag] = value
    return changes


def build_preset_change_map(preset_names: Sequence[str]) -> ChangeMap:
    changes: ChangeMap = {}
    for preset_name in preset_names:
        key = preset_name.lower()
        preset = PRESETS.get(key)
        if preset is None:
            available = ", ".join(sorted(PRESETS)) or "<없음>"
            raise SystemExit(f"[오류] 알 수 없는 preset입니다: {preset_name} (사용 가능: {available})")
        changes.update(normalize_changes(preset.changes))
    return changes


def resolve_changes(preset_names: Sequence[str], pairs: Sequence[str]) -> ChangeMap:
    changes = build_preset_change_map(preset_names)
    changes.update(build_change_map(pairs))
    return changes


def print_manual_usage() -> None:
    print("[사용법]")
    print("  python incar_change.py TAG1 VALUE1 TAG2 VALUE2 ...")
    print("  python incar_change.py --preset PRESET_NAME [TAG VALUE ...]")
    print("")
    print("[예시]")
    print("  python incar_change.py ENCUT 520 ISMEAR -5")
    print("  python incar_change.py LDAU '#'   # 주석 처리")
    print("  python incar_change.py --preset dos")
    print("  python incar_change.py --preset zpe")
    print("  python incar_change.py --preset dos NEDOS 3000   # preset 적용 후 직접 입력값으로 덮어쓰기")
    print("")
    print("[참고]")
    print("  - 기본적으로 현재 디렉터리의 INCAR 파일만 수정합니다.")
    print("  - 다른 파일을 수정하려면 -f 또는 --file 옵션을 사용합니다.")
    print("  - TAG 뒤에 '#'를 넣으면 해당 태그 줄을 주석 처리합니다.")
    print("  - preset 규칙은 코드 상단의 PRESETS 딕셔너리에 추가합니다.")


def print_preset_list() -> None:
    print("[preset 목록]")
    if not PRESETS:
        print("  <등록된 preset 없음>")
        return

    for name, preset in sorted(PRESETS.items()):
        count = len(preset.changes)
        status = f"{count}개 태그" if count else "태그 규칙 미등록"
        print(f"  - {name}: {preset.description} ({status})")


def _read_lines(path: str) -> List[str]:
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return f.readlines()
    except UnicodeDecodeError:
        with open(path, "r") as f:
            return f.readlines()


def _comment_padding(before_comment: str) -> str:
    """'!' 주석 앞 공백을 보존하고, 없으면 기본 2칸을 사용."""
    m = re.search(r"([ \t]*)$", before_comment)
    if not m:
        return "  "
    trailing = m.group(1)
    return trailing if trailing else "  "


def _split_inline_comment(line: str) -> Tuple[str, str, str, str]:
    if "!" not in line:
        return line, "", "", ""

    before_comment, sep, after_comment = line.partition("!")
    return before_comment, sep, after_comment, _comment_padding(before_comment)


def _compose_line(before: str, sep: str, after_comment: str, keep_newline: bool, pad: str = "") -> str:
    if sep:
        line = before + pad + sep + after_comment
        if not line.endswith("\n"):
            line += "\n"
        return line
    if keep_newline:
        return before + "\n"
    return before


def transform_incar_lines(lines: Sequence[str], changes: Mapping[str, str]) -> Tuple[bool, List[str]]:
    """INCAR 라인 목록에 변경 사항을 적용하고, 실제 변경 여부와 새 라인을 반환."""
    normalized_changes = normalize_changes(changes)
    changed = False
    remaining = set(normalized_changes.keys())
    new_lines: List[str] = []

    for line in lines:
        original_line = line
        before_comment, sep, after_comment, comment_pad = _split_inline_comment(line)

        stripped = before_comment.lstrip()
        leading_ws = before_comment[: len(before_comment) - len(stripped)]

        # 이전에 '#'로 주석 처리된 태그도 인식해서, 값 변경 요청이면 주석을 해제합니다.
        if stripped.startswith(COMMENT_VALUE):
            candidate = stripped[1:]
            m_hash = _TAG_LINE_RE.match(candidate.lstrip())
            if m_hash:
                _inner_ws, tag, eq_sign, _rest = m_hash.groups()
                tag_upper = tag.upper()
                if tag_upper in remaining:
                    value = normalized_changes[tag_upper]
                    if value == COMMENT_VALUE:
                        remaining.discard(tag_upper)
                    else:
                        new_before = f"{leading_ws}{tag}{eq_sign} {value}"
                        line = _compose_line(
                            new_before, sep, after_comment, original_line.endswith("\n"), comment_pad
                        )
                        remaining.discard(tag_upper)
                        if line != original_line:
                            changed = True

            new_lines.append(line)
            continue

        m = _TAG_LINE_RE.match(before_comment)
        if m:
            leading_ws_match, tag, eq_sign, rest = m.groups()
            tag_upper = tag.upper()
            if tag_upper in remaining:
                value = normalized_changes[tag_upper]
                if value == COMMENT_VALUE:
                    new_before = f"{leading_ws_match}# {tag}{eq_sign}{rest}"
                    line = _compose_line(
                        new_before, sep, after_comment, original_line.endswith("\n"), comment_pad
                    )
                else:
                    new_before = f"{leading_ws_match}{tag}{eq_sign} {value}"
                    line = _compose_line(
                        new_before, sep, after_comment, original_line.endswith("\n"), comment_pad
                    )
                remaining.discard(tag_upper)
                if line != original_line:
                    changed = True

        new_lines.append(line)

    # 파일에 없던 태그는 마지막에 추가합니다. 단, 주석 처리 요청("#")은 추가하지 않습니다.
    to_add = [tag for tag in sorted(remaining) if normalized_changes[tag] != COMMENT_VALUE]
    if to_add:
        changed = True
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"
        new_lines.append("\n")
        for tag in to_add:
            new_lines.append(f"{tag} = {normalized_changes[tag]}\n")

    return changed, new_lines


def update_incar(path: str, changes: Mapping[str, str]) -> bool:
    """단일 INCAR 파일에서 태그 값을 변경한다. 실제 변경이 있으면 True 반환."""
    lines = _read_lines(path)
    changed, new_lines = transform_incar_lines(lines, changes)

    if changed:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

    return changed


def get_tag_values(path: str, target_tags: Sequence[str]) -> Tuple[Dict[str, str], Set[str]]:
    """파일에서 주어진 태그들의 값과 주석 여부를 추출한다.

    Returns: (tag -> value dict, commented tag set)
    """
    targets = {normalize_tag(tag) for tag in target_tags}
    found: Dict[str, str] = {}
    commented: Set[str] = set()

    lines = _read_lines(path)

    for line in lines:
        before_comment, _, _, _ = _split_inline_comment(line)

        stripped = before_comment.lstrip()
        is_hash = stripped.startswith(COMMENT_VALUE)
        candidate = stripped[1:].lstrip() if is_hash else stripped

        m = _TAG_LINE_RE.match(candidate)
        if not m:
            continue

        _leading_ws, tag, _eq_sign, rest = m.groups()
        tag_upper = tag.upper()
        if tag_upper not in targets or tag_upper in found:
            continue

        found[tag_upper] = rest.strip()
        if is_hash:
            commented.add(tag_upper)

        if len(found) == len(targets):
            break

    return found, commented


def print_change_summary(
    tags: Sequence[str],
    changes: Mapping[str, str],
    before_values: Mapping[str, str],
    before_commented: Set[str],
    after_values: Mapping[str, str],
    after_commented: Set[str],
) -> None:
    print("[요약] 태그별 변경 내용:")
    for tag in sorted(tags):
        before = before_values.get(tag)
        after = after_values.get(tag)
        before_c = tag in before_commented
        after_c = tag in after_commented
        req_comment = changes.get(tag) == COMMENT_VALUE

        if req_comment:
            if before is not None and not before_c and after_c:
                print(f"  - {tag}: {before} -> <주석 처리>")
            elif before is not None and before_c:
                print(f"  - {tag}: 변경 없음 (이미 주석 처리됨)")
            elif before is None:
                print(f"  - {tag}: <없음> (주석 처리 대상 없음)")
            else:
                print(f"  - {tag}: {before} -> <주석 처리>")
        elif before is None and after is not None:
            print(f"  - {tag}: <없음> -> {after}")
        elif before is not None and after is not None and (before != after or before_c != after_c):
            suffix = " (주석 해제)" if before_c and not after_c else ""
            print(f"  - {tag}: {before} -> {after}{suffix}")
        elif before is not None and after is not None and before == after and not after_c:
            print(f"  - {tag}: 변경 없음 ({after})")
        else:
            print(f"  - {tag}: <값 없음>")


def main() -> None:
    args = parse_args()

    if args.list_presets:
        print_preset_list()
        return

    if not args.pairs and not args.presets:
        print_manual_usage()
        return

    changes = resolve_changes(args.presets, args.pairs)
    if not changes:
        print("[알림] 적용할 태그 변경이 없습니다.")
        if args.presets:
            print("  선택한 preset에 아직 태그 규칙이 등록되지 않았습니다.")
            print("  코드 상단의 PRESETS 딕셔너리에 규칙을 추가한 뒤 다시 실행하세요.")
        return

    path = args.file
    if not os.path.isfile(path):
        print(f"[오류] INCAR 파일을 찾을 수 없습니다: {path}")
        return

    tags = list(changes.keys())
    before_values, before_commented = get_tag_values(path, tags)

    changed = update_incar(path, changes)

    after_values, after_commented = get_tag_values(path, tags)

    print_change_summary(tags, changes, before_values, before_commented, after_values, after_commented)


if __name__ == "__main__":
    main()
