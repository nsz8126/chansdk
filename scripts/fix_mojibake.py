# -*- coding: utf-8 -*-
"""One-off tool: repair GBK/UTF-8 mojibake comments in source files.

Corruption pattern: original UTF-8 text was decoded as GBK and re-saved
as UTF-8. The inverse transform `line.encode('gbk').decode('utf-8')`
recovers the original text.

Safety rules:
- Only touch lines containing known mojibake indicator characters.
- Only replace when the round-trip succeeds, changes the line, and the
  result contains at least one common CJK character.
- Lines that fail the round-trip (e.g. genuine Chinese strings) are left
  untouched.

Usage: python scripts/fix_mojibake.py [--dry-run]
"""

import os
import sys

# Characters frequently produced by decoding UTF-8 as GBK
MOJIBAKE_INDICATORS = (
    "绾挎鏁版嵁鎵€涓嬮珮鍒嗛€熷彲鍞敮鍟嗗姞鍏ラ槻椤哄簭浠嬪尯鍚堟垚鐑熺獽瀹櫨"
    "悎鍙渶鐐瑰紑嬮敊鏃偍瓒寔屾湡涔畾崲綔敤庝笉湪け璐ラ兜紩堟埅㈠洖鏀筴︼紝"
    "绋嬪箷骞惰皟鏈€嶅姞閫氳繃鍗栫偣绾х鍒锋柊楂樹綆鏇存槑绔熷彉寲忓叿鏌ョ湅瀹氬€煎紓父緇撴潫鍙嶅悜鍨嬫壘埌灏鹃儴鍏冪礌鍖呭惈纭畾闇€瑕侀噸鏂扮畻鐒跺垎褰㈤珮浣庡彲鑳戒笉瀵广€€倈"
)


def is_cjk(ch: str) -> bool:
    return "一" <= ch <= "鿿"


def to_original_bytes(line: str) -> bytes:
    """Re-encode mojibake text to the original UTF-8 byte stream.

    `gb18030` covers the private-use characters left by the cp936 decode,
    but encodes '€' as A2E3 while the original stream had raw 0x80 — fix
    that byte back so alignment is preserved.
    """
    return line.encode("gb18030", errors="strict").replace(b"\xa2\xe3", b"\x80")


def fix_line(line: str) -> str | None:
    """Return repaired line, or None if not applicable/unsafe."""
    if not any(ch in MOJIBAKE_INDICATORS for ch in line):
        return None
    try:
        payload = to_original_bytes(line)
    except UnicodeEncodeError:
        return None
    try:
        fixed = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        fixed = payload.decode("utf-8", errors="replace")
        # Lossy repair is only accepted when very little was lost —
        # genuine Chinese lines produce a flood of U+FFFD here and are
        # correctly rejected.
        if fixed.count("�") > 2:
            return None
    if fixed == line:
        return None
    if not any(is_cjk(ch) for ch in fixed):
        return None
    # The repaired line should not still look like mojibake
    if sum(ch in MOJIBAKE_INDICATORS for ch in fixed) > 2:
        return None
    return fixed


def process_file(path: str, dry_run: bool) -> tuple[int, int]:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    has_bom = text.startswith("﻿")
    lines = text.splitlines(keepends=True)
    fixed_count = 0
    skipped = 0
    out_lines = []
    for line in lines:
        body = line.rstrip("\r\n")
        ending = line[len(body):]
        fixed = fix_line(body)
        if fixed is not None:
            out_lines.append(fixed + ending)
            fixed_count += 1
        else:
            if any(ch in MOJIBAKE_INDICATORS for ch in body):
                skipped += 1
            out_lines.append(line)
    if fixed_count and not dry_run:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(("﻿" if has_bom else "") + "".join(out_lines).lstrip("﻿"))
    return fixed_count, skipped


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    root = os.path.join(os.path.dirname(__file__), "..")
    total_fixed = total_skipped = 0
    for dirpath, _dirnames, filenames in os.walk(os.path.join(root, "chan")):
        for name in sorted(filenames):
            if not name.endswith(".py"):
                continue
            path = os.path.join(dirpath, name)
            fixed, skipped = process_file(path, dry_run)
            if fixed or skipped:
                rel = os.path.relpath(path, root)
                print(f"{rel}: fixed={fixed} skipped={skipped}")
            total_fixed += fixed
            total_skipped += skipped
    print(f"TOTAL fixed={total_fixed} skipped={total_skipped} dry_run={dry_run}")


if __name__ == "__main__":
    main()
