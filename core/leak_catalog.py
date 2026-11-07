"""P5.3 泄露规则目录。

把“创建函数 -> 类型 -> 销毁函数 -> 风险等级”从修复器中独立出来，并为每条
规则补齐证据文本、置信度、修复级别和不适用条件。规则层只消费 P5.2 的
`CreationSite` 事实，不做任何源码匹配，也不直接改写脚本。

分级约定：

- A：可以自动修复。只有局部点、局部单位组、新建玩家组，并且必须通过
  逃逸、共享、长期持有、循环、多出口和无法解析等护栏；L09 只追加置空。
- B：只生成补丁建议。矩形、特效/闪电、内联单位组/玩家组、boolexpr；
  GUI 单位组（L08）只解释为什么不改。
- C：只报告。共享句柄与长期计时器/触发器/哈希表，禁止销毁。
"""

from __future__ import annotations

from dataclasses import dataclass

from core.constants import (
    ALL_LEAK_TYPES,
    BOOLEXPR_FUNCS,
    EFFECT_FUNCS,
    FORCE_FUNCS,
    GROUP_FUNCS,
    LIGHTNING_FUNCS,
    LOC_FUNCS,
    RECT_FUNCS,
    SHARED_HANDLE_CREATORS,
)
from core.jass_semantics import (
    TRACKED_HANDLE_TYPES,
    CreationSite,
    ScriptSemantics,
    TYPE_BY_CREATOR,
)

# 只有这些新建玩家组函数进入 A 级白名单；GetPlayersAll 是共享对象，永不销毁。
FORCE_AUTO_WHITELIST = frozenset(
    {"CreateForce", "GetPlayersMatching", "GetPlayersInIsntance"}
) - SHARED_HANDLE_CREATORS

LEVELS = ("A", "B", "C")
FIX_MODES = ("auto", "patch", "report", "none")


@dataclass(frozen=True, slots=True)
class LeakRule:
    id: str
    title: str
    level: str
    handle_types: tuple[str, ...]
    creators: frozenset[str] | None
    destroyer: str | None
    confidence: float
    fix_mode: str
    shared_or_global: bool
    long_lived: bool
    auto_whitelist: bool
    auxiliary: bool
    evidence: str
    conditions: tuple[str, ...]
    exclusions: tuple[str, ...]


RULES: tuple[LeakRule, ...] = (
    LeakRule(
        id="L01",
        title="局部点与内联点",
        level="A",
        handle_types=("location",),
        creators=frozenset(LOC_FUNCS),
        destroyer="RemoveLocation",
        confidence=0.95,
        fix_mode="auto",
        shared_or_global=False,
        long_lived=False,
        auto_whitelist=True,
        auxiliary=False,
        evidence=(
            "`{function}` 第 {line} 行的 {handle_type} 由 `{creator}` 创建，"
            "函数出口前未调用 `{destroyer}`。"
        ),
        conditions=(
            "局部变量或可直接提升的内联创建",
            "未写入全局、数组、哈希表，未传给未知函数",
            "不存在提前返回，循环内绑定的局部变量除外",
            "函数内所有语句均可解析",
        ),
        exclusions=(
            "共享句柄与长期对象",
            "GUI bj_wantDestroyGroup 管理的单位组",
            "销毁前已置空或仅部分路径销毁",
        ),
    ),
    LeakRule(
        id="L02",
        title="局部单位组",
        level="A",
        handle_types=("group",),
        creators=frozenset(GROUP_FUNCS),
        destroyer="DestroyGroup",
        confidence=0.90,
        fix_mode="auto",
        shared_or_global=False,
        long_lived=False,
        auto_whitelist=True,
        auxiliary=False,
        evidence=(
            "`{function}` 第 {line} 行的单位组由 `{creator}` 创建，"
            "函数出口前未调用 `{destroyer}`。"
        ),
        conditions=(
            "局部变量且未逃逸",
            "不被 bj_wantDestroyGroup 接管",
            "函数不存在提前返回",
        ),
        exclusions=(
            "GUI 管理的单位组",
            "GetPlayersAll 等共享创建函数",
            "只在一个分支内销毁",
        ),
    ),
    LeakRule(
        id="L03",
        title="新建玩家组",
        level="A",
        handle_types=("force",),
        creators=FORCE_AUTO_WHITELIST,
        destroyer="DestroyForce",
        confidence=0.90,
        fix_mode="auto",
        shared_or_global=False,
        long_lived=False,
        auto_whitelist=True,
        auxiliary=False,
        evidence=(
            "`{function}` 第 {line} 行的玩家组由 `{creator}` 新建，"
            "函数出口前未调用 `{destroyer}`。"
        ),
        conditions=(
            "创建函数属于 A 级白名单",
            "局部变量且未逃逸",
        ),
        exclusions=(
            "GetPlayersAll 返回的共享 force",
            "GetPlayersMatching 返回的临时组仍被返回或存入容器",
        ),
    ),
    LeakRule(
        id="L04",
        title="矩形与区域",
        level="B",
        handle_types=("rect",),
        creators=frozenset(RECT_FUNCS),
        destroyer="RemoveRect",
        confidence=0.80,
        fix_mode="patch",
        shared_or_global=False,
        long_lived=False,
        auto_whitelist=False,
        auxiliary=False,
        evidence=(
            "`{function}` 第 {line} 行的矩形由 `{creator}` 创建，"
            "函数出口前未调用 `{destroyer}`；本版只生成补丁建议。"
        ),
        conditions=("矩形没有被 RegionAddRect 接管", "矩形未写入全局变量"),
        exclusions=("RegionAddRect 已接管所有权", "全局矩形初始化"),
    ),
    LeakRule(
        id="L05",
        title="特效与闪电",
        level="B",
        handle_types=("effect", "lightning"),
        creators=frozenset(EFFECT_FUNCS + LIGHTNING_FUNCS),
        destroyer=None,
        confidence=0.75,
        fix_mode="patch",
        shared_or_global=False,
        long_lived=False,
        auto_whitelist=False,
        auxiliary=False,
        evidence=(
            "`{function}` 第 {line} 行的 {handle_type} 由 `{creator}` 创建，"
            "未调用 `{destroyer}`；本版只报告并生成补丁建议。"
        ),
        conditions=("特效/闪电没有交给其他系统长期持有", "句柄没有被返回或存入容器"),
        exclusions=("全局或共享特效", "无法确认接收方的自定义封装"),
    ),
    LeakRule(
        id="L06",
        title="内联单位组与玩家组",
        level="B",
        handle_types=("group", "force"),
        creators=frozenset(GROUP_FUNCS + FORCE_FUNCS),
        destroyer=None,
        confidence=0.70,
        fix_mode="patch",
        shared_or_global=False,
        long_lived=False,
        auto_whitelist=False,
        auxiliary=False,
        evidence=(
            "`{function}` 第 {line} 行内联创建的 {handle_type} 没有赋给变量，"
            "无法在函数出口统一清理；本版只生成补丁建议。"
        ),
        conditions=("内联调用没有作为返回值转移", "外层不是销毁函数或 RegionAddRect"),
        exclusions=("内联点按 L01 自动处理", "GUI 管理的单位组", "共享 force"),
    ),
    LeakRule(
        id="L07",
        title="boolexpr 条件与过滤器",
        level="B",
        handle_types=("boolexpr",),
        creators=frozenset(BOOLEXPR_FUNCS),
        destroyer="DestroyBoolExpr",
        confidence=0.70,
        fix_mode="patch",
        shared_or_global=False,
        long_lived=False,
        auto_whitelist=False,
        auxiliary=False,
        evidence=(
            "`{function}` 第 {line} 行的 boolexpr 由 `{creator}` 创建，"
            "未调用 `{destroyer}`；本版只报告并生成补丁建议。"
        ),
        conditions=("boolexpr 没有通过 TriggerAddCondition 注册为长期对象",),
        exclusions=("已注册到触发器条件", "作为回调注册到其他系统"),
    ),
    LeakRule(
        id="L08",
        title="GUI 单位组",
        level="B",
        handle_types=("group",),
        creators=frozenset(GROUP_FUNCS),
        destroyer="DestroyGroup",
        confidence=0.90,
        fix_mode="report",
        shared_or_global=False,
        long_lived=False,
        auto_whitelist=False,
        auxiliary=False,
        evidence=(
            "`{function}` 第 {line} 行的单位组处于 bj_wantDestroyGroup + "
            "ForGroupBJ 流程，销毁由 GUI 枚举负责，禁止追加 DestroyGroup。"
        ),
        conditions=("函数设置 bj_wantDestroyGroup = true", "单位组通过 ForGroupBJ 枚举"),
        exclusions=("函数内自行创建并持有的普通单位组",),
    ),
    LeakRule(
        id="L09",
        title="销毁后未置空 agent 变量",
        level="A",
        handle_types=tuple(sorted(TRACKED_HANDLE_TYPES)),
        creators=None,
        destroyer=None,
        confidence=0.85,
        fix_mode="auto",
        shared_or_global=False,
        long_lived=False,
        auto_whitelist=False,
        auxiliary=True,
        evidence=(
            "`{function}` 第 {line} 行的 `{variable}` 已销毁，但未执行 "
            "`set {variable} = null`；追加置空可避免悬空引用。"
        ),
        conditions=("局部 agent 变量已完整销毁", "销毁后没有再次使用该变量"),
        exclusions=("内联临时句柄", "销毁前已置空", "仅部分路径销毁"),
    ),
    LeakRule(
        id="L10",
        title="共享句柄与长期对象",
        level="C",
        handle_types=tuple(sorted(TRACKED_HANDLE_TYPES)),
        creators=None,
        destroyer=None,
        confidence=0.99,
        fix_mode="report",
        shared_or_global=True,
        long_lived=True,
        auto_whitelist=False,
        auxiliary=False,
        evidence=(
            "`{function}` 第 {line} 行的 {handle_type} 由 `{creator}` 创建，"
            "属于共享句柄或长期对象类别；任何自动销毁都会破坏引擎或地图状态。"
        ),
        conditions=("创建函数返回共享对象，或句柄已注册为长期对象",),
        exclusions=("函数内独立创建、未注册且未共享的普通句柄",),
    ),
)

RULE_BY_ID = {rule.id: rule for rule in RULES}


@dataclass(slots=True)
class CatalogMatch:
    creation: CreationSite
    rule: LeakRule | None
    level: str
    confidence: float
    finding: bool
    notice: bool
    fix_mode: str
    evidence: str
    reasons: tuple[str, ...] = ()
    auxiliary: tuple["CatalogMatch", ...] = ()

    @property
    def rule_id(self):
        return self.rule.id if self.rule else None

    @property
    def auto_fixable(self):
        return (
            self.finding
            and self.fix_mode == "auto"
            and self.rule is not None
            and not self.rule.auxiliary
        )


def rule_for_creator(creator):
    """返回创建函数的类型与销毁函数；未知创建函数返回 (None, None)。"""
    handle_type = TYPE_BY_CREATOR.get(creator)
    if not handle_type:
        return None, None
    entry = _destroyer_for_type(handle_type)
    return handle_type, entry


def rules_for_type(handle_type):
    return [rule for rule in RULES if handle_type in rule.handle_types]


def _destroyer_for_type(handle_type):
    entry = ALL_LEAK_TYPES.get(handle_type)
    return entry[0] if entry else None


def _rule_for(creation):
    handle_type = creation.handle_type
    if creation.kind == "inline":
        if handle_type == "location":
            return RULE_BY_ID["L01"]
        if handle_type in ("group", "force"):
            return RULE_BY_ID["L06"]
    if handle_type == "location":
        return RULE_BY_ID["L01"]
    if handle_type == "group":
        return RULE_BY_ID["L02"]
    if handle_type == "force":
        return RULE_BY_ID["L03"]
    if handle_type == "rect":
        return RULE_BY_ID["L04"]
    if handle_type in ("effect", "lightning"):
        return RULE_BY_ID["L05"]
    if handle_type == "boolexpr":
        return RULE_BY_ID["L07"]
    if handle_type in ("timer", "trigger", "hashtable"):
        return RULE_BY_ID["L10"]
    return None


def _variable_label(creation):
    return f"`{creation.variable}`" if creation.variable else "内联临时句柄"


def _evidence(rule, creation, suffix=""):
    destroyer = rule.destroyer or _destroyer_for_type(creation.handle_type) or "对应的销毁函数"
    text = rule.evidence.format(
        function=creation.function,
        line=creation.line,
        creator=creation.creator,
        handle_type=creation.handle_type,
        variable=creation.variable or "内联临时句柄",
        destroyer=destroyer,
    )
    if suffix:
        text = f"{text}{suffix}"
    return text


def _dedupe(items):
    return tuple(dict.fromkeys(item for item in items if item))


def _null_advice(creation):
    if creation.kind != "local" or not creation.variable:
        return None
    if creation.cleanup not in ("complete", "cleaned"):
        return None
    if not creation.destroys or creation.releases:
        return None
    rule = RULE_BY_ID["L09"]
    return CatalogMatch(
        creation=creation,
        rule=rule,
        level=rule.level,
        confidence=rule.confidence,
        finding=False,
        notice=False,
        fix_mode=rule.fix_mode,
        evidence=_evidence(rule, creation),
        reasons=("销毁后未置空",),
    )


def _match(rule, creation, *, finding, notice, fix_mode, reasons=(), auxiliary=()):
    return CatalogMatch(
        creation=creation,
        rule=rule,
        level=rule.level,
        confidence=rule.confidence,
        finding=finding,
        notice=notice,
        fix_mode=fix_mode,
        evidence=_evidence(rule, creation),
        reasons=_dedupe(reasons),
        auxiliary=tuple(item for item in auxiliary if item is not None),
    )


def classify_creation(creation):
    """把一条创建事实归类为规则结果；不修改 creation 本身。"""
    # 共享/长期优先于全局：全局共享 force 也要明确解释“禁止销毁”。
    if creation.shared or creation.long_lived:
        reasons = []
        if creation.shared:
            reasons.append("共享句柄，禁止销毁")
        if creation.long_lived:
            reasons.append("长期对象，禁止销毁")
        if creation.kind == "global":
            reasons.append("由全局变量持有")
        return _match(
            RULE_BY_ID["L10"],
            creation,
            finding=False,
            notice=True,
            fix_mode="report",
            reasons=tuple(reasons) + tuple(creation.reasons),
        )

    if creation.kind == "global":
        return CatalogMatch(
            creation=creation,
            rule=None,
            level="C",
            confidence=1.0,
            finding=False,
            notice=True,
            fix_mode="none",
            evidence=(
                f"`{creation.variable}` 是全局变量，生命周期由全局持有；"
                "不在函数内销毁，也不列为泄露。"
            ),
            reasons=("全局持有",),
        )

    if creation.gui_managed or creation.cleanup == "managed":
        return _match(
            RULE_BY_ID["L08"],
            creation,
            finding=False,
            notice=True,
            fix_mode="report",
            reasons=("由 GUI 的 bj_wantDestroyGroup 管理",),
        )

    rule = _rule_for(creation)
    if rule is None:
        return CatalogMatch(
            creation=creation,
            rule=None,
            level="C",
            confidence=0.5,
            finding=False,
            notice=True,
            fix_mode="none",
            evidence=f"`{creation.creator}` 返回的 {creation.handle_type} 未纳入类型目录。",
            reasons=("未纳入类型目录",),
        )

    if creation.status == "escaped":
        escape_kinds = {fact.kind for fact in creation.escapes}
        silent = escape_kinds <= {"return", "ownership_sink"}
        if creation.escapes:
            details = "；".join(
                sorted({fact.description for fact in creation.escapes})
            )
            suffix = f"所有权已转移：{details}"
        else:
            suffix = "所有权已转移。"
        result = _match(
            rule,
            creation,
            finding=False,
            notice=not silent,
            fix_mode="none",
            reasons=tuple(creation.reasons),
        )
        result.evidence = f"{result.evidence}{suffix}"
        return result

    if creation.status == "cleaned":
        return _match(
            rule,
            creation,
            finding=False,
            notice=False,
            fix_mode="none",
            reasons=tuple(creation.reasons),
            auxiliary=(_null_advice(creation),),
        )

    if creation.status == "leaked":
        fix_mode = rule.fix_mode
        if fix_mode == "auto" and not (
            creation.auto_fix and rule.auto_whitelist
        ):
            fix_mode = "patch"
        finding = rule.level in ("A", "B") and not rule.auxiliary
        return _match(
            rule,
            creation,
            finding=finding,
            notice=rule.level == "C",
            fix_mode=fix_mode,
            reasons=tuple(creation.reasons),
        )

    return _match(
        rule,
        creation,
        finding=False,
        notice=True,
        fix_mode="none",
        reasons=tuple(creation.reasons),
    )


def classify_semantics(semantics: ScriptSemantics):
    return [classify_creation(item) for item in semantics.iter_creations()]


def leak_findings(matches):
    return [match for match in matches if match.finding]


def auto_fix_matches(matches):
    return [match for match in matches if match.auto_fixable]


def coverage_statement():
    """返回可直接放进报告/文档的覆盖范围声明。"""
    types = sorted(
        {handle_type for rule in RULES for handle_type in rule.handle_types}
        | set(TRACKED_HANDLE_TYPES)
    )
    return "\n".join(
        (
            "P5.3 规则覆盖范围：",
            "- 自动修复（A）：L01 局部点与内联点、L02 局部单位组、"
            "L03 新建玩家组；L09 只追加 set null。",
            "- 补丁建议（B）：L04 矩形/区域、L05 特效/闪电、"
            "L06 内联单位组/玩家组、L07 boolexpr；L08 GUI 单位组只解释不写盘。",
            "- 只报告（C）：L10 共享句柄与长期计时器/触发器/哈希表。",
            f"- 已纳入类型目录：{', '.join(types)}。",
            "- 不处理：单位、物品、可破坏物、region、音效、对话框等未纳管句柄；"
            "Lua 脚本不支持写入。",
            "- 全局变量持有的普通句柄不视为泄露，也不会自动销毁。",
        )
    )
