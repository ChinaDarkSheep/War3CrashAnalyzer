from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.constants import ALL_LEAK_TYPES
from core.fixer import Fixer

CORPUS_DIR = Path(__file__).resolve().parent
REPO_ROOT = CORPUS_DIR.parents[1]
DEFAULT_MANIFEST = CORPUS_DIR / "corpus.json"
BASELINE_PATH = CORPUS_DIR / "baseline.json"

DEFAULT_OPTIONS = {
    "fix_point": True,
    "fix_group": True,
    "fix_rect": True,
    "optimize_jass": True,
}


def load_manifest(path: Path = DEFAULT_MANIFEST) -> Dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as f:
        manifest = json.load(f)
    cases = manifest.get("cases") or []
    ids = [case.get("id") for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("corpus.json 中存在重复的 id")
    for case in cases:
        case_path = CORPUS_DIR / case["file"]
        if not case_path.is_file():
            raise FileNotFoundError(f"语料文件不存在: {case_path}")
    return manifest


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalise_finding(finding: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "function": finding.get("function"),
        "variable": finding.get("variable"),
        "type": finding.get("type"),
        "line": finding.get("line"),
    }


def _match_expected(
    expected: List[Dict[str, Any]], actual: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    used = set()
    matched: List[Dict[str, Any]] = []
    missed: List[Dict[str, Any]] = []

    for wanted in expected:
        for index, got in enumerate(actual):
            if index in used:
                continue
            if wanted.get("function") and got.get("function") != wanted["function"]:
                continue
            if wanted.get("type") and got.get("type") != wanted["type"]:
                continue
            if wanted.get("variable") and got.get("variable") != wanted["variable"]:
                continue
            used.add(index)
            matched.append({"expected": wanted, "actual": got})
            break
        else:
            missed.append(wanted)

    extras = [got for index, got in enumerate(actual) if index not in used]
    return matched, missed, extras


def _destroy_count(text: str, destroyer: str, variable: str) -> int:
    pattern = rf"\b{re.escape(destroyer)}\s*\(\s*{re.escape(variable)}\s*\)"
    return len(re.findall(pattern, text))


def _function_texts(text: str) -> Dict[str, str]:
    lines = text.replace("\r\n", "\n").split("\n")
    blocks: Dict[str, str] = {}
    for index, line in enumerate(lines):
        if not re.match(r"^function\s", line):
            continue
        end = index + 1
        while end < len(lines) and not re.match(r"^endfunction\s*$", lines[end]):
            end += 1
        name = re.match(r"^function\s+(\S+)", line)
        if name:
            blocks[name.group(1)] = "\n".join(lines[index:end + 1])
    return blocks


def _destroyer_for_type(handle_type: str) -> Optional[str]:
    entry = ALL_LEAK_TYPES.get(handle_type)
    return entry[0] if entry else None


def _guarded_returns(text: str, destroyer: str, variable: str) -> Dict[str, int]:
    lines = text.splitlines()
    pattern = re.compile(rf"\b{re.escape(destroyer)}\s*\(\s*{re.escape(variable)}\s*\)")
    total = 0
    guarded = 0
    for index, line in enumerate(lines):
        if not re.match(r"^\s*return\b", line):
            continue
        total += 1
        window = lines[max(0, index - 4):index]
        if any(pattern.search(item) for item in window):
            guarded += 1
    return {"total": total, "guarded": guarded}


def _count_findings_by_type(findings: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for finding in findings:
        key = finding.get("type") or "unknown"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def analyze_case(case: Dict[str, Any], options: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "id": case["id"],
        "file": case["file"],
        "intent": case.get("intent", ""),
        "level": case.get("level", ""),
        "expected_count": len(case.get("expected_findings") or []),
        "actual_count": 0,
        "matched_count": 0,
        "missed": [],
        "extras": [],
        "findings": [],
        "nfuncs": 0,
        "leak_counter": 0,
        "source_sha256": None,
        "fixed_sha256": None,
        "fixed_length": 0,
        "fixed_equals_source": False,
        "fixed_text": None,
        "idempotent": False,
        "guarded_returns": None,
        "destroy_counts": [],
        "must_fix": [],
        "forbidden_hits": [],
        "violations": [],
        "error": None,
    }

    try:
        text = (CORPUS_DIR / case["file"]).read_text(encoding="utf-8")
        fixer = Fixer(lambda _message: None)
        findings = fixer.locate_leaks(text, options)
        normalised = [_normalise_finding(item) for item in findings]

        fixer.leak_counter = 0
        fixed, nfuncs = fixer.transform_script(text, options)
        second_fixer = Fixer(lambda _message: None)
        fixed_again, _ = second_fixer.transform_script(fixed, options)

        result["findings"] = normalised
        result["actual_count"] = len(normalised)
        result["nfuncs"] = nfuncs
        result["leak_counter"] = fixer.leak_counter
        result["source_sha256"] = _sha256_text(text)
        result["fixed_sha256"] = _sha256_text(fixed)
        result["fixed_length"] = len(fixed)
        result["fixed_equals_source"] = fixed == text
        result["fixed_text"] = fixed
        result["idempotent"] = fixed_again == fixed

        matched, missed, extras = _match_expected(
            case.get("expected_findings") or [], normalised
        )
        result["matched_count"] = len(matched)
        result["missed"] = missed
        result["extras"] = extras

        if missed:
            result["violations"].append(
                "finding_missed:" + ",".join(
                    f"{item.get('function')}/{item.get('type')}/{item.get('variable')}"
                    for item in missed
                )
            )
        if not result["idempotent"]:
            result["violations"].append("not_idempotent")

        for check in case.get("destroy_checks") or []:
            destroyer = check["destroyer"]
            variable = check["variable"]
            count = _destroy_count(fixed, destroyer, variable)
            minimum = int(check.get("min", 0))
            maximum = int(check.get("max", count))
            result["destroy_counts"].append(
                {
                    "destroyer": destroyer,
                    "variable": variable,
                    "count": count,
                    "min": minimum,
                    "max": maximum,
                }
            )
            if count < minimum:
                result["violations"].append(
                    f"destroy_missing:{destroyer}({variable})={count}<{minimum}"
                )
            if count > maximum:
                result["violations"].append(
                    f"destroy_extra:{destroyer}({variable})={count}>{maximum}"
                )

        for pattern in case.get("must_fix_patterns") or []:
            hit = bool(re.search(pattern, fixed, re.MULTILINE))
            result["must_fix"].append({"pattern": pattern, "hit": hit})
            if not hit:
                result["violations"].append(f"must_fix_missing:{pattern}")

        for pattern in case.get("forbidden_fix_patterns") or []:
            hit = bool(re.search(pattern, fixed, re.MULTILINE))
            result["forbidden_hits"].append({"pattern": pattern, "hit": hit})
            if hit:
                result["violations"].append(f"forbidden_fix:{pattern}")

        expected_guarded = case.get("expected_guarded_returns")
        expected_findings = case.get("expected_findings") or []
        if expected_guarded is not None and expected_findings:
            wanted = expected_findings[0]
            destroyer = _destroyer_for_type(wanted.get("type") or "")
            variable = wanted.get("variable")
            if destroyer and variable:
                guarded = _guarded_returns(fixed, destroyer, variable)
                guarded["expected"] = int(expected_guarded)
                result["guarded_returns"] = guarded
                if guarded["guarded"] < guarded["expected"]:
                    result["violations"].append(
                        "guarded_returns:"
                        f"{guarded['guarded']}/{guarded['total']}"
                        f"<{guarded['expected']}"
                    )

    except Exception as exc:  # noqa: BLE001 - 基线需要记录而不是中断
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["violations"].append("analysis_error")

    return result


def analyze_corpus(manifest_path: Path = DEFAULT_MANIFEST) -> Dict[str, Any]:
    manifest = load_manifest(manifest_path)
    options = dict(DEFAULT_OPTIONS)
    options.update(manifest.get("options") or {})
    cases = [analyze_case(case, options) for case in manifest.get("cases") or []]

    expected_total = sum(case["expected_count"] for case in cases)
    actual_total = sum(case["actual_count"] for case in cases)
    matched_total = sum(case["matched_count"] for case in cases)
    violation_total = sum(len(case["violations"]) for case in cases)

    summary = {
        "cases": len(cases),
        "expected_findings": expected_total,
        "actual_findings": actual_total,
        "matched_findings": matched_total,
        "missed_findings": expected_total - matched_total,
        "extra_findings": actual_total - matched_total,
        "precision": (matched_total / actual_total) if actual_total else 1.0,
        "recall": (matched_total / expected_total) if expected_total else 1.0,
        "idempotent_cases": sum(1 for case in cases if case["idempotent"]),
        "cases_with_violations": sum(1 for case in cases if case["violations"]),
        "violations": violation_total,
        "analysis_errors": sum(1 for case in cases if case["error"]),
    }

    return {
        "corpus_version": manifest.get("version", 0),
        "manifest": str(Path(manifest_path).resolve().relative_to(REPO_ROOT)),
        "summary": summary,
        "cases": cases,
    }


def build_snapshot(report: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "corpus_version": report["corpus_version"],
        "summary": report["summary"],
        "cases": [
            {
                "id": case["id"],
                "level": case["level"],
                "expected_count": case["expected_count"],
                "actual_count": case["actual_count"],
                "matched_count": case["matched_count"],
                "missed": case["missed"],
                "extras": case["extras"],
                "nfuncs": case["nfuncs"],
                "leak_counter": case["leak_counter"],
                "source_sha256": case["source_sha256"],
                "fixed_sha256": case["fixed_sha256"],
                "fixed_length": case["fixed_length"],
                "fixed_equals_source": case["fixed_equals_source"],
                "idempotent": case["idempotent"],
                "guarded_returns": case["guarded_returns"],
                "destroy_counts": case["destroy_counts"],
                "must_fix": case["must_fix"],
                "forbidden_hits": case["forbidden_hits"],
                "violations": case["violations"],
                "error": case["error"],
            }
            for case in report["cases"]
        ],
    }


def write_baseline(snapshot: Dict[str, Any], path: Path = BASELINE_PATH) -> Path:
    path = Path(path)
    path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    return path


def load_baseline(path: Path = BASELINE_PATH) -> Dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def format_report(report: Dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "P5.0 泄露语料基线",
        f"用例: {summary['cases']}",
        (
            f"发现: 期望 {summary['expected_findings']} / 实际 {summary['actual_findings']} / "
            f"命中 {summary['matched_findings']}"
        ),
        (
            f"precision: {summary['precision']:.1%}  "
            f"recall: {summary['recall']:.1%}  "
            f"误报 {summary['extra_findings']} 漏报 {summary['missed_findings']}"
        ),
        (
            f"幂等: {summary['idempotent_cases']}/{summary['cases']}  "
            f"违规: {summary['violations']}  "
            f"异常: {summary['analysis_errors']}"
        ),
        "",
    ]
    for case in report["cases"]:
        status = "OK" if not case["violations"] else f"{len(case['violations'])} 违规"
        lines.append(
            f"[{case['id']}] {case['level'] or '-'} "
            f"findings={case['actual_count']}/{case['expected_count']} "
            f"matched={case['matched_count']} "
            f"idem={'Y' if case['idempotent'] else 'N'} {status}"
        )
        for violation in case["violations"]:
            lines.append(f"    - {violation}")
        if case["error"]:
            lines.append(f"    ! {case['error']}")
    return "\n".join(lines)


def analyze_real_maps(
    map_dir: Path,
    out_dir: Path,
    mpq_editor: Path,
    limit: int = 10,
) -> Dict[str, Any]:
    """对本地真实地图做可选基线；只写指标和哈希，不落盘脚本内容。"""
    map_dir = Path(map_dir)
    out_dir = Path(out_dir)
    if not map_dir.is_dir():
        raise NotADirectoryError(f"地图目录不存在: {map_dir}")
    if not Path(mpq_editor).is_file():
        raise FileNotFoundError(f"MPQEditor 不存在: {mpq_editor}")

    out_dir.mkdir(parents=True, exist_ok=True)
    maps = [
        path
        for path in sorted(map_dir.iterdir())
        if path.suffix.lower() in {".w3x", ".w3m"}
        and "_leakfixed" not in path.stem.lower()
    ][: max(0, limit)]

    entries: List[Dict[str, Any]] = []
    for map_path in maps:
        entry: Dict[str, Any] = {
            "file": map_path.name,
            "size": map_path.stat().st_size,
            "sha256": _sha256_file(map_path),
            "script": None,
            "script_sha256": None,
            "script_length": 0,
            "nfuncs": 0,
            "findings": 0,
            "finding_types": {},
            "leak_counter": 0,
            "fixed_sha256": None,
            "idempotent": False,
            "duplicate_destroys": [],
            "error": None,
        }
        temp_dir = Path(tempfile.mkdtemp(prefix="leak_baseline_", dir=str(out_dir)))
        try:
            fixer = Fixer(lambda _message: None)
            script_path = fixer._extract_script(
                str(map_path), str(mpq_editor), str(temp_dir)
            )
            if not script_path:
                entry["error"] = "extract_failed"
                entries.append(entry)
                continue
            script_path = Path(script_path)
            text = script_path.read_text(encoding="utf-8", errors="ignore")
            entry["script"] = script_path.name
            entry["script_sha256"] = _sha256_text(text)
            entry["script_length"] = len(text)

            findings = fixer.locate_leaks(text, DEFAULT_OPTIONS)
            entry["findings"] = len(findings)
            entry["finding_types"] = _count_findings_by_type(findings)

            fixer.leak_counter = 0
            fixed, nfuncs = fixer.transform_script(text, DEFAULT_OPTIONS)
            second_fixer = Fixer(lambda _message: None)
            fixed_again, _ = second_fixer.transform_script(fixed, DEFAULT_OPTIONS)
            entry["nfuncs"] = nfuncs
            entry["leak_counter"] = fixer.leak_counter
            entry["fixed_sha256"] = _sha256_text(fixed)
            entry["idempotent"] = fixed_again == fixed

            source_funcs = _function_texts(text)
            fixed_funcs = _function_texts(fixed)
            for finding in findings:
                destroyer = _destroyer_for_type(finding.get("type") or "")
                variable = finding.get("variable") or ""
                if not destroyer or not variable or variable.startswith("Anonymous"):
                    continue
                source_block = source_funcs.get(finding.get("function"))
                fixed_block = fixed_funcs.get(finding.get("function"))
                if not source_block or not fixed_block:
                    continue
                before = _destroy_count(source_block, destroyer, variable)
                after = _destroy_count(fixed_block, destroyer, variable)
                if before >= 1 and after > before:
                    entry["duplicate_destroys"].append(
                        {
                            "function": finding.get("function"),
                            "destroyer": destroyer,
                            "variable": variable,
                            "before": before,
                            "after": after,
                        }
                    )
        except Exception as exc:  # noqa: BLE001 - 基线记录失败地图
            entry["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
        entries.append(entry)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "map_dir": str(map_dir),
        "maps": entries,
    }
    (out_dir / "real_baseline.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def format_real_report(report: Dict[str, Any]) -> str:
    lines = [f"真实地图基线: {len(report['maps'])} 张"]
    for entry in report["maps"]:
        status = entry["error"] or "OK"
        lines.append(
            f"[{entry['file']}] script={entry['script'] or '-'} "
            f"funcs={entry['nfuncs']} findings={entry['findings']} "
            f"idem={'Y' if entry['idempotent'] else 'N'} {status}"
        )
    return "\n".join(lines)
