"""P6 真实地图掉线风险扫描器（只记录哈希与指标）。

不保存脚本正文，不写回地图。输出用于人工复核精度：

    python tests/run_desync_report.py --maps "<地图目录>" --limit 12
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.desync_risk import scan_text  # noqa: E402
from core.map_script import MapScript  # noqa: E402

DEFAULT_OUTPUT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "desync_corpus", ".real_baseline", "desync_baseline.json")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MPQ_EDITOR = os.environ.get(
    "WAR3_MPQ_EDITOR", os.path.join(ROOT, "MPQEditor.exe"))


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_maps(directory, limit):
    found = []
    for root, _dirs, files in os.walk(directory):
        for name in files:
            if name.lower().endswith((".w3x", ".w3m", ".w3n")):
                found.append(os.path.join(root, name))
        if limit and len(found) >= limit:
            break
    return sorted(found)[:limit] if limit else sorted(found)


def scan_one(path, work_dir, mpq_editor=None):
    started = time.perf_counter()
    record = {
        "file": os.path.basename(path),
        "size": os.path.getsize(path),
        "sha256": sha256_file(path),
        "error": None,
    }
    try:
        script = MapScript.load(
            path, work_dir,
            mpq_editor_path=mpq_editor if os.path.isfile(mpq_editor or "")
            else None)
        report = scan_text(script.text, script.language)
    except Exception as exc:  # noqa: BLE001 - 单图失败不影响整批
        record["error"] = str(exc)
        record["elapsed"] = round(time.perf_counter() - started, 3)
        return record

    record.update({
        "script": script.internal_path or script.script_path,
        "script_sha256": script.source_sha256,
        "language": report.language,
        "lines": report.total_lines,
        "coverage": round(report.coverage, 4),
        "parse_errors": report.parse_errors,
        "level": report.level,
        "findings": len(report.findings),
        "by_severity": report.counts(),
        "by_rule": report.rule_counts(),
        "finding_brief": [
            {
                "rule": item.rule_id,
                "severity": item.severity,
                "function": item.function,
                "line": item.line,
            }
            for item in report.findings[:50]
        ],
        "elapsed": round(time.perf_counter() - started, 3),
    })
    return record


def summarize(records):
    done = [item for item in records if not item.get("error")]
    language = {}
    rules = {}
    severity = {"高": 0, "中": 0, "低": 0}
    for item in done:
        language[item["language"]] = language.get(item["language"], 0) + 1
        for key, value in item["by_rule"].items():
            rules[key] = rules.get(key, 0) + value
        for key, value in item["by_severity"].items():
            severity[key] = severity.get(key, 0) + value
    coverage = [item["coverage"] for item in done] or [0]
    return {
        "maps": len(records),
        "scanned": len(done),
        "failed": len(records) - len(done),
        "languages": language,
        "findings": sum(item["findings"] for item in done),
        "by_severity": severity,
        "by_rule": rules,
        "coverage_min": min(coverage),
        "coverage_avg": round(sum(coverage) / len(coverage), 4),
        "elapsed": round(sum(item.get("elapsed", 0) for item in records), 2),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--maps", required=True, help="地图目录")
    parser.add_argument("--limit", type=int, default=12, help="最多扫描数量")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="JSON 输出路径")
    parser.add_argument("--mpq-editor", default=DEFAULT_MPQ_EDITOR,
                        help="MPQEditor.exe 路径")
    parser.add_argument("--json", action="store_true", help="打印 JSON")
    args = parser.parse_args(argv)

    paths = collect_maps(args.maps, args.limit)
    if not paths:
        parser.error(f"未找到地图: {args.maps}")

    work_dir = os.path.join(os.path.dirname(args.output), "work")
    records = []
    for index, path in enumerate(paths, start=1):
        print(f"[{index}/{len(paths)}] {os.path.basename(path)}", flush=True)
        record = scan_one(path, work_dir, args.mpq_editor)
        records.append(record)
        if record["error"]:
            print(f"    失败: {record['error']}", flush=True)
        else:
            print(
                f"    {record['language']} {record['lines']} 行 · "
                f"覆盖 {record['coverage']:.1%} · "
                f"{record['findings']} 条 {record['by_rule']} · "
                f"{record['elapsed']:.2f}s", flush=True)

    summary = summarize(records)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "map_dir": os.path.abspath(args.maps),
        "summary": summary,
        "maps": records,
    }
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    print("\n汇总: " + json.dumps(summary, ensure_ascii=False))
    print(f"已写入: {args.output}")
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
