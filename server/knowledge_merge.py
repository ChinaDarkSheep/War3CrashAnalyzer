"""案例合并进共享知识库：预览、冲突判定、备份、原子写入与缓存热更新。"""

import json
import os
import shutil
import tempfile
import threading
from datetime import datetime

import settings
from common import normalize_offset, normalize_version

_LOCK = threading.Lock()
CONFIRMED_SOURCES = {"作者确认", "维护者确认"}


class KnowledgeError(Exception):
    pass


def load_knowledge():
    try:
        with open(settings.KNOWLEDGE_PATH, 'r', encoding='utf-8') as handle:
            kb = json.load(handle)
    except Exception as exc:
        raise KnowledgeError(f"知识库读取失败：{exc}") from exc
    if not isinstance(kb, dict):
        raise KnowledgeError("知识库格式无效")
    kb.setdefault('modules', {})
    return kb


def _module_key(kb, module):
    for key in (kb.get('modules') or {}):
        if key.lower() == module.lower():
            return key
    return module


def preview_case(case, kb):
    """计算目标地址、冲突与不可合并原因；列表、导出和合并共用同一套口径。"""
    result = {
        'mergeable': False,
        'reason': None,
        'module': None,
        'version': None,
        'offset': None,
        'target': None,
        'conflict': False,
        'existing': None,
        'new_version': False,
    }
    module = (case.get('module') or '').strip()
    if not module or module.lower() == 'unknown':
        result['reason'] = '缺少模块名'
        return result
    version = (case.get('game_version') or '').strip()
    if version:
        version = normalize_version(version) or version
    if not version:
        result['reason'] = '缺少游戏版本'
        return result
    offset = normalize_offset(case.get('relative_offset'))
    if not offset:
        result['reason'] = '模块内偏移无效'
        return result
    if not (case.get('cause') or '').strip():
        result['reason'] = '案例结论为空'
        return result

    module_key = _module_key(kb, module)
    versions = (kb.get('modules') or {}).get(module_key) or {}
    existing = (versions.get(version) or {}).get(offset)
    result.update({
        'mergeable': True,
        'module': module_key,
        'version': version,
        'offset': offset,
        'target': f"{module_key} / {version} / {offset}",
        'conflict': existing is not None,
        'existing': existing,
        'new_version': version not in versions,
    })
    return result


def build_entry(case, existing=None):
    """案例 → knowledge.json 条目；覆盖时保留原有归属/建议/API 线索。"""
    try:
        confidence = float(case.get('confidence'))
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = round(min(1.0, max(0.0, confidence)), 2)
    source = (case.get('source') or '').strip()
    entry = dict(existing or {})
    entry.update({
        'desc': (case.get('cause') or '').strip(),
        'source': f"case/{case.get('signature')}",
        'confidence': confidence,
        'verified': bool(existing and existing.get('verified'))
                    or source in CONFIRMED_SOURCES,
    })
    return entry


def merge_cases(cases, overwrite=False, dry_run=False):
    """批量写入知识库；返回 (逐条结果, 实际变更数)。写入在进程内串行化。"""
    with _LOCK:
        try:
            kb = load_knowledge()
        except KnowledgeError as exc:
            return ([{'signature': case.get('signature'), 'status': 'error',
                      'reason': str(exc)} for case in cases], 0)
        results = []
        changed = 0
        for case in cases:
            preview = preview_case(case, kb)
            base = {'signature': case.get('signature'), 'target': preview['target']}
            if not preview['mergeable']:
                results.append({**base, 'status': 'invalid', 'reason': preview['reason']})
                continue
            if preview['conflict'] and not overwrite:
                results.append({**base, 'status': 'conflict',
                                'reason': '知识库已存在同地址条目',
                                'existing': preview['existing']})
                continue
            entry = build_entry(case, preview['existing'] if preview['conflict'] else None)
            versions = kb.setdefault('modules', {}).setdefault(preview['module'], {})
            offsets = versions.setdefault(preview['version'], {})
            offsets[preview['offset']] = entry
            changed += 1
            results.append({
                **base,
                'status': 'preview' if dry_run else 'merged',
                'reason': None,
                'created': not preview['conflict'],
                'entry': entry,
                'merged_key': f"{preview['module']}/{preview['version']}/{preview['offset']}",
            })
        if changed and not dry_run:
            try:
                kb.setdefault('_meta', {})['updated'] = datetime.now().strftime('%Y-%m-%d')
                _write_knowledge(kb)
            except KnowledgeError as exc:
                for item in results:
                    if item['status'] == 'merged':
                        item['status'] = 'error'
                        item['reason'] = str(exc)
                return results, 0
            _reload_runtime(kb)
        return results, changed


def export_fragment(cases, kb=None):
    """导出可直接合并进 knowledge.json 的片段；冲突条目保留原有附加字段。"""
    kb = kb if kb is not None else load_knowledge()
    fragment = {'modules': {}}
    skipped = []
    for case in cases:
        preview = preview_case(case, kb)
        if not preview['mergeable']:
            skipped.append({'signature': case.get('signature'),
                            'reason': preview['reason']})
            continue
        versions = fragment['modules'].setdefault(preview['module'], {})
        offsets = versions.setdefault(preview['version'], {})
        offsets[preview['offset']] = build_entry(
            case, preview['existing'] if preview['conflict'] else None)
    return fragment, skipped


def _write_knowledge(kb):
    path = settings.KNOWLEDGE_PATH
    directory = os.path.dirname(path) or '.'
    temp_path = None
    try:
        os.makedirs(settings.KNOWLEDGE_BACKUP_DIR, exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        shutil.copy2(path, os.path.join(
            settings.KNOWLEDGE_BACKUP_DIR, f"knowledge-{stamp}.json"))
        _prune_backups()
        fd, temp_path = tempfile.mkstemp(
            prefix='.knowledge-', suffix='.tmp', dir=directory)
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(kb, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
        os.replace(temp_path, path)
    except Exception as exc:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        raise KnowledgeError(f"知识库写入失败：{exc}") from exc


def _prune_backups():
    try:
        names = sorted((name for name in os.listdir(settings.KNOWLEDGE_BACKUP_DIR)
                        if name.startswith('knowledge-') and name.endswith('.json')),
                       reverse=True)
        for name in names[settings.KNOWLEDGE_BACKUP_KEEP:]:
            os.remove(os.path.join(settings.KNOWLEDGE_BACKUP_DIR, name))
    except OSError as exc:
        print(f"[!] 知识库备份清理失败: {exc}")


def _reload_runtime(kb):
    """让服务端诊断立即用上新条目，无需重启。"""
    settings.KB = kb
    prefixes = kb.get('build_prefixes') or {}
    settings.BUILD_PREFIXES.clear()
    settings.BUILD_PREFIXES.update(prefixes)
    try:
        import core.knowledge as core_kb
        core_kb._KB = kb
        core_kb.EXCEPTION_CODES = kb.get('exceptions', {})
        core_kb.CRASH_KNOWLEDGE = kb.get('modules', {})
        core_kb.DISPUTED = kb.get('disputed', {})
        core_kb.BUILD_PREFIXES = prefixes
    except Exception as exc:
        print(f"[!] 客户端知识库缓存热更新失败（重启后生效）: {exc}")
