"""P5.4 地图脚本读写封装。

只负责“拿到脚本 / 写回副本 / 备份 / 撤销 / 重新提取校验”，不生成修复内容。
安全边界：

- 原图永远只读；所有写回都落到 ``*_leakfixed`` 副本。
- 写回前备份已存在的副本，``undo()`` 可恢复上一次内容。
- 写回后立即重新提取脚本，文本必须与写入内容一致，否则回滚。
- Lua 脚本一律只读，``write_count`` 为 0。
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from core.map_extract import (
    build_dynamic_listfile,
    extract_script,
    guess_internal_path,
)

_SCRIPT_SUFFIXES = {".j": "jass", ".lua": "lua"}


def _creation_flags():
    if os.name == "nt":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def decode_script(raw):
    """返回 (text, encoding)；优先 UTF-8(BOM)，失败回退 GBK。"""
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig"), "utf-8-sig"
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return raw.decode("gbk", errors="replace"), "gbk"


def encode_script(text, encoding):
    if encoding == "utf-8-sig":
        return text.encode("utf-8-sig")
    if encoding == "gbk":
        try:
            return text.encode("gbk")
        except UnicodeEncodeError:
            return text.encode("utf-8")
    return text.encode("utf-8")


def normalize_text(text):
    return (text or "").replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")


@dataclass(slots=True)
class ScriptWriteResult:
    written: bool
    write_count: int
    output_path: str | None = None
    backup_path: str | None = None
    verification: dict = field(default_factory=dict)
    error: str | None = None
    readonly: bool = False


@dataclass(slots=True)
class MapScript:
    source_path: str
    kind: str  # map / script / directory
    script_path: str
    internal_path: str | None
    language: str
    text: str
    encoding: str
    method: str
    writable: bool
    readonly_reason: str | None = None
    listfile: str | None = None
    extract_dir: str | None = None
    mpq_editor_path: str | None = None
    work_dir: str | None = None
    source_sha256: str | None = None
    _temp_dir: str | None = None
    _last_output: str | None = None
    _last_backup: str | None = None
    _last_preexisting: bool = False

    @classmethod
    def load(
        cls,
        source,
        work_dir,
        mpq_editor_path=None,
        w3x2lni_path=None,
        log=None,
    ):
        log = log or (lambda _message: None)
        source_path = os.path.abspath(str(source))
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"输入不存在: {source_path}")
        work_dir = os.path.abspath(str(work_dir))
        os.makedirs(work_dir, exist_ok=True)

        kind = "directory" if os.path.isdir(source_path) else "map"
        if not os.path.isdir(source_path):
            suffix = os.path.splitext(source_path)[1].lower()
            if suffix in _SCRIPT_SUFFIXES:
                kind = "script"

        if kind == "script":
            script_path = source_path
            language = _SCRIPT_SUFFIXES[os.path.splitext(source_path)[1].lower()]
            internal_path = os.path.basename(source_path)
            method = "脚本文件"
            listfile = None
            extract_dir = None
        else:
            result = extract_script(
                source_path,
                mpq_editor_path,
                work_dir,
                w3x2lni_path=w3x2lni_path,
                log=log,
            )
            script_path = result.get("script_path")
            if not script_path:
                raise ValueError(
                    result.get("error") or "未能从输入中提取到主脚本"
                )
            script_path = os.path.abspath(script_path)
            language = _SCRIPT_SUFFIXES.get(
                os.path.splitext(script_path)[1].lower(), "jass"
            )
            internal_path = result.get("internal_path")
            method = result.get("method") or ""
            listfile = result.get("listfile")
            extract_dir = result.get("extract_dir")
            if not internal_path and extract_dir:
                internal_path = guess_internal_path(script_path, extract_dir)

        raw = Path(script_path).read_bytes()
        text, encoding = decode_script(raw)

        writable = True
        reason = None
        if kind == "directory":
            writable = False
            reason = "目录输入只读；请选择地图或脚本文件。"
        elif language == "lua":
            writable = False
            reason = "检测到 Lua 脚本，本版只读，不写入地图。"
        elif kind == "map" and not internal_path:
            writable = False
            reason = "无法确定地图内部脚本路径，拒绝写入。"
        elif kind == "map" and not (mpq_editor_path and os.path.isfile(mpq_editor_path)):
            writable = False
            reason = "缺少 MPQEditor，无法写回地图副本。"

        return cls(
            source_path=source_path,
            kind=kind,
            script_path=script_path,
            internal_path=internal_path,
            language=language,
            text=text,
            encoding=encoding,
            method=method,
            writable=writable,
            readonly_reason=reason,
            listfile=listfile,
            extract_dir=extract_dir,
            mpq_editor_path=os.path.abspath(mpq_editor_path) if mpq_editor_path else None,
            work_dir=work_dir,
            source_sha256=sha256_file(
                source_path if kind != "directory" else script_path
            ),
            _temp_dir=extract_dir,
        )

    @property
    def output_path(self):
        if self.kind == "directory":
            return None
        stem, suffix = os.path.splitext(self.source_path)
        return f"{stem}_leakfixed{suffix}"

    @property
    def source_unchanged(self):
        path = self.source_path if self.kind != "directory" else self.script_path
        return sha256_file(path) == self.source_sha256

    def write(self, text, verify=True):
        if not self.writable:
            return ScriptWriteResult(
                written=False,
                write_count=0,
                error=self.readonly_reason or "当前输入不可写",
                readonly=True,
            )

        output = self.output_path
        if not output:
            return ScriptWriteResult(
                written=False, write_count=0, error="没有可写输出路径"
            )
        os.makedirs(os.path.dirname(output) or ".", exist_ok=True)

        backup = None
        preexisting = os.path.exists(output)
        if preexisting:
            backup = output + ".bak"
            shutil.copy2(output, backup)

        self._last_output = output
        self._last_backup = backup
        self._last_preexisting = preexisting

        try:
            if self.kind == "script":
                self._write_text(output, text)
            else:
                self._write_map(output, text)
        except Exception as exc:  # noqa: BLE001 - 写回失败需要回滚
            self._rollback()
            return ScriptWriteResult(
                written=False,
                write_count=0,
                output_path=output,
                backup_path=backup,
                error=f"写回失败：{type(exc).__name__}: {exc}",
            )

        verification = {}
        if verify:
            verification = self.verify(output, text)
            if not verification.get("verified"):
                self._rollback()
                return ScriptWriteResult(
                    written=False,
                    write_count=0,
                    output_path=output,
                    backup_path=backup,
                    verification=verification,
                    error=verification.get("error") or "重新提取校验失败，已回滚",
                )

        return ScriptWriteResult(
            written=True,
            write_count=1,
            output_path=output,
            backup_path=backup,
            verification=verification,
        )

    def verify(self, output_path=None, expected_text=None):
        output_path = output_path or self._last_output or self.output_path
        expected_text = self.text if expected_text is None else expected_text
        actual = self._read_output_text(output_path)
        if actual is None:
            return {
                "verified": False,
                "expected_sha256": sha256_text(expected_text),
                "actual_sha256": None,
                "expected_length": len(expected_text),
                "actual_length": 0,
                "error": "写回后无法重新提取脚本",
            }
        expected_norm = normalize_text(expected_text)
        actual_norm = normalize_text(actual)
        return {
            "verified": expected_norm == actual_norm,
            "expected_sha256": sha256_text(expected_norm),
            "actual_sha256": sha256_text(actual_norm),
            "expected_length": len(expected_norm),
            "actual_length": len(actual_norm),
            "error": None if expected_norm == actual_norm else "重新提取的脚本文本不一致",
        }

    def undo(self):
        output = self._last_output
        if not output:
            return False
        if self._last_backup and os.path.exists(self._last_backup):
            shutil.copy2(self._last_backup, output)
            os.remove(self._last_backup)
        elif not self._last_preexisting and os.path.exists(output):
            os.remove(output)
        self._last_output = None
        self._last_backup = None
        self._last_preexisting = False
        return True

    def cleanup(self):
        if self._temp_dir and os.path.isdir(self._temp_dir):
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None

    def _write_text(self, path, text):
        with open(path, "wb") as f:
            f.write(encode_script(text, self.encoding))

    def _write_map(self, output, text):
        shutil.copy2(self.source_path, output)
        temp_dir = tempfile.mkdtemp(prefix="leakfix_write_", dir=self.work_dir)
        try:
            fixed_script = os.path.join(
                temp_dir, os.path.basename(self.internal_path)
            )
            self._write_text(fixed_script, text)
            command = [
                self.mpq_editor_path,
                "/add",
                output,
                fixed_script,
                self.internal_path,
            ]
            result = subprocess.run(
                command,
                capture_output=True,
                timeout=300,
                creationflags=_creation_flags(),
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"MPQEditor /add 退出码 {result.returncode}: "
                    f"{result.stdout[:200]!r}"
                )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _read_output_text(self, output_path):
        if not output_path or not os.path.exists(output_path):
            return None
        if self.kind == "script":
            raw = Path(output_path).read_bytes()
            return decode_script(raw)[0]
        if not self.internal_path or not self.mpq_editor_path:
            return None
        temp_dir = tempfile.mkdtemp(prefix="leakfix_verify_", dir=self.work_dir)
        try:
            listfile = build_dynamic_listfile(output_path, temp_dir)
            subprocess.run(
                [
                    self.mpq_editor_path,
                    "/extract",
                    output_path,
                    self.internal_path,
                    temp_dir,
                    "/listfile",
                    listfile,
                ],
                capture_output=True,
                timeout=300,
                creationflags=_creation_flags(),
            )
            candidate = os.path.join(
                temp_dir, *self.internal_path.replace("/", "\\").split("\\")
            )
            if not os.path.exists(candidate):
                candidate = os.path.join(
                    temp_dir, os.path.basename(self.internal_path)
                )
            if not os.path.exists(candidate):
                wanted = os.path.basename(self.internal_path).lower()
                for root, _, filenames in os.walk(temp_dir):
                    for name in filenames:
                        if name.lower() == wanted:
                            candidate = os.path.join(root, name)
                            break
                    if os.path.exists(candidate):
                        break
            if not os.path.exists(candidate):
                return None
            return decode_script(Path(candidate).read_bytes())[0]
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _rollback(self):
        output = self._last_output
        if not output:
            return
        if self._last_backup and os.path.exists(self._last_backup):
            shutil.copy2(self._last_backup, output)
            os.remove(self._last_backup)
        elif not self._last_preexisting and os.path.exists(output):
            os.remove(output)
