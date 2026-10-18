#!/usr/bin/env python3
"""Safe, copy-only batch renamer and CSV summarizer for disposable practice data."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

MANIFEST_FIELDS = {"source_filename", "target_filename", "approved"}
DATA_FIELDS = {"date", "store", "item", "quantity", "amount"}


def inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def safe_basename(value: str) -> bool:
    return bool(value) and value not in {".", ".."} and Path(value).name == value and "/" not in value and "\\" not in value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames or []), list(reader)


def validate(source_dir: Path, manifest_path: Path, output_dir: Path):
    problems: list[str] = []
    source_root = source_dir.resolve()
    output_root = output_dir.resolve()
    manifest = manifest_path.resolve()

    if not source_root.is_dir():
        problems.append(f"來源目錄不存在：{source_root}")
    if not manifest.is_file():
        problems.append(f"清單檔不存在：{manifest}")
    if output_root.exists():
        problems.append(f"輸出目錄已存在，為避免覆蓋而拒絕：{output_root}")
    if (output_root == source_root or inside(output_root, source_root)
            or inside(source_root, output_root)):
        problems.append("來源目錄與輸出目錄不能相同，也不能互相包含")
    if problems:
        return [], [], problems

    fieldnames, rows = read_csv(manifest)
    missing_fields = sorted(MANIFEST_FIELDS - set(fieldnames))
    if missing_fields:
        problems.append("清單缺少欄位：" + ", ".join(missing_fields))
        return [], [], problems
    if not rows:
        problems.append("清單沒有資料行")

    plan: list[tuple[Path, str]] = []
    seen_sources: set[str] = set()
    seen_targets: set[str] = set()
    for line_no, row in enumerate(rows, start=2):
        source_name = (row.get("source_filename") or "").strip()
        target_name = (row.get("target_filename") or "").strip()
        approved = (row.get("approved") or "").strip().lower()
        row_label = f"第 {line_no} 行"
        if not safe_basename(source_name):
            problems.append(f"{row_label}來源檔名必須是單一檔名：{source_name!r}")
            continue
        if not safe_basename(target_name) or Path(target_name).suffix.lower() != ".csv":
            problems.append(f"{row_label}目標必須是單一 .csv 檔名：{target_name!r}")
            continue
        if approved != "yes":
            problems.append(f"{row_label}未明確核准；approved 必須為 yes")
        source_key = source_name.casefold()
        target_key = target_name.casefold()
        if source_key in seen_sources:
            problems.append(f"{row_label}來源重複：{source_name}")
        if target_key in seen_targets:
            problems.append(f"{row_label}目標檔名重複：{target_name}")
        seen_sources.add(source_key)
        seen_targets.add(target_key)
        source_path = (source_root / source_name).resolve()
        if not inside(source_path, source_root):
            problems.append(f"{row_label}來源路徑超出來源目錄：{source_name}")
            continue
        if not source_path.is_file():
            problems.append(f"{row_label}找不到來源檔：{source_name}")
            continue
        plan.append((source_path, target_name))

    # Validate every CSV completely before making any output directory.
    transactions: list[tuple[str, str, str, Decimal, Decimal]] = []
    for source_path, _ in plan:
        try:
            columns, data_rows = read_csv(source_path)
        except (OSError, UnicodeError, csv.Error) as exc:
            problems.append(f"無法讀取 {source_path.name}：{exc}")
            continue
        missing_data = sorted(DATA_FIELDS - set(columns))
        if missing_data:
            problems.append(f"{source_path.name} 缺少資料欄位：{', '.join(missing_data)}")
            continue
        if not data_rows:
            problems.append(f"{source_path.name} 沒有資料行")
            continue
        for data_line, record in enumerate(data_rows, start=2):
            try:
                quantity = Decimal((record.get("quantity") or "").strip())
                amount = Decimal((record.get("amount") or "").strip())
                if not quantity.is_finite() or not amount.is_finite():
                    raise InvalidOperation
                if not all([(record.get("date") or "").strip(),
                            (record.get("store") or "").strip(),
                            (record.get("item") or "").strip()]):
                    raise ValueError("date/store/item 不可空白")
                transactions.append((record["store"].strip(), record["item"].strip(),
                                     record["date"].strip(), quantity, amount))
            except (InvalidOperation, ValueError) as exc:
                problems.append(f"{source_path.name} 第 {data_line} 行數值或必填欄位無效：{exc}")
    return plan, transactions, problems


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="先預演、核對後才複製並彙總 CSV；永不改動來源檔")
    parser.add_argument("--source-dir", required=True, type=Path, help="練習來源檔資料夾")
    parser.add_argument("--manifest", required=True, type=Path, help="需含 source_filename,target_filename,approved 欄位")
    parser.add_argument("--output-dir", required=True, type=Path, help="必須是尚不存在的新目錄")
    parser.add_argument("--apply", action="store_true", help="完成預演與人工確認後才建立輸出；未指定時只預演")
    args = parser.parse_args()

    plan, transactions, problems = validate(args.source_dir, args.manifest, args.output_dir)
    if problems:
        print("BLOCKED：未執行任何複製。請先逐項修正並重新預演：")
        for problem in problems:
            print(f"- {problem}")
        return 2

    print(f"預演通過：{len(plan)} 個檔案；來源不會被修改。")
    for source_path, target_name in plan:
        print(f"  {source_path.name}  ->  copied/{target_name}")
    print(f"預計彙總 {len(transactions)} 筆資料到 summary.csv")
    print(f"輸出目錄：{args.output_dir.resolve()}")
    if not args.apply:
        print("目前是預演模式；人工核對以上清單後，才可加 --apply。")
        return 0

    output_root = args.output_dir.resolve()
    copied_dir = output_root / "copied"
    output_root.mkdir(parents=True, exist_ok=False)
    copied_dir.mkdir()
    import shutil

    manifest_rows: list[dict[str, str]] = []
    for source_path, target_name in plan:
        target_path = copied_dir / target_name
        shutil.copy2(source_path, target_path)
        manifest_rows.append({"source_filename": source_path.name,
                              "target_filename": target_name,
                              "source_sha256": sha256(source_path),
                              "output_sha256": sha256(target_path)})

    totals: dict[tuple[str, str], list[Decimal]] = defaultdict(lambda: [Decimal("0"), Decimal("0")])
    for store, item, _, quantity, amount in transactions:
        totals[(store, item)][0] += quantity
        totals[(store, item)][1] += amount
    summary_rows = [{"store": store, "item": item,
                     "total_quantity": format(values[0], "f"),
                     "total_amount": format(values[1], "f")}
                    for (store, item), values in sorted(totals.items())]
    write_csv(output_root / "summary.csv",
              ["store", "item", "total_quantity", "total_amount"], summary_rows)
    write_csv(output_root / "copy_manifest.csv",
              ["source_filename", "target_filename", "source_sha256", "output_sha256"], manifest_rows)
    run_record = {"created_at_utc": datetime.now(timezone.utc).isoformat(),
                  "source_dir": str(args.source_dir.resolve()),
                  "manifest": str(args.manifest.resolve()),
                  "copied_files": len(plan), "source_rows": len(transactions),
                  "summary_rows": len(summary_rows), "mode": "copy-only"}
    (output_root / "run_record.json").write_text(
        json.dumps(run_record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已写入新输出目录：{output_root}")
    print(f"复制文件：{len(plan)}；汇总行：{len(summary_rows)}；來源仍保留原样。")
    print("如需回滚，请按 reference/验收答案与回滚说明.md 隔离此输出目录；脚本不会删除任何文件。")
    return 0


if __name__ == "__main__":
    sys.exit(main())


