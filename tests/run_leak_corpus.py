#!/usr/bin/env python
"""P5.0 泄露语料运行器。

用法：
    python tests/run_leak_corpus.py
    python tests/run_leak_corpus.py --write-baseline
    python tests/run_leak_corpus.py --maps "D:\\War3Maps" --limit 10

真实地图模式只输出哈希与指标，不落盘脚本内容，避免版权与仓库体积问题。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.leak_corpus import runner  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="P5.0 泄露语料基线运行器")
    parser.add_argument(
        "--manifest",
        default=str(runner.DEFAULT_MANIFEST),
        help="语料清单路径",
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="把当前结果写入 tests/leak_corpus/baseline.json",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出 JSON（不输出人类可读报告）",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="存在违规时返回退出码 1",
    )
    parser.add_argument("--maps", help="可选：真实地图目录")
    parser.add_argument(
        "--out",
        default=str(runner.CORPUS_DIR / ".real_baseline"),
        help="真实地图基线输出目录（默认已加入 .gitignore）",
    )
    parser.add_argument(
        "--mpq",
        default=str(REPO_ROOT / "MPQEditor.exe"),
        help="MPQEditor 路径",
    )
    parser.add_argument("--limit", type=int, default=10, help="真实地图最多分析数量")
    args = parser.parse_args(argv)

    report = runner.analyze_corpus(Path(args.manifest))
    snapshot = runner.build_snapshot(report)

    if args.write_baseline:
        written = runner.write_baseline(snapshot)
        if not args.json:
            print(f"基线已写入: {written}")

    real_report = None
    if args.maps:
        real_report = runner.analyze_real_maps(
            Path(args.maps), Path(args.out), Path(args.mpq), args.limit
        )

    if args.json:
        payload = {"corpus": snapshot}
        if real_report is not None:
            payload["real_maps"] = real_report
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(runner.format_report(report))
        if real_report is not None:
            print()
            print(runner.format_real_report(real_report))

    if args.strict and report["summary"]["violations"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
