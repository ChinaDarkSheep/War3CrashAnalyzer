import re

COMMON_DICT = [
    'war3map.w3u', 'war3map.w3a', 'war3map.w3h', 'war3map.w3t', 'war3map.w3q',
    'war3map.w3b', 'war3map.w3d', 'war3map.w3e', 'war3map.w3i', 'war3map.wtg',
    'war3map.wct', 'war3map.w3r', 'war3map.w3c', 'war3map.w3s', 'war3map.wpm',
    'war3map.j', 'war3map.lua', 'scripts\\war3map.j', '(listfile)'
]

# --- JASS 泄露定位&修复常量 ---
GROUP_FUNCS = [
    "GetUnitsOfPlayerAndTypeId", "GetUnitsInRangeOfLocMatching", "GetUnitsOfPlayerMatching", 
    "GetUnitsInRectMatching", "GetUnitsOfTypeIdAll", "GetUnitsOfPlayerAll", 
    "GetUnitsInRangeOfLocAll", "GetUnitsInRectOfPlayer", "GetUnitsInRectAll",
    "GetUnitsSelectedAll", "GetRandomSubGroup", "CreateGroup",
    "YDWEGetRandomSubGroupNull", "YDWEGetUnitsInRangeOfLocAllNull", 
    "YDWEGetUnitsInRectAllNull", "YDWEGetUnitsOfPlayerAllNull"
]
LOC_FUNCS = [
    "GetUnitLoc", "GetRandomLocInRect", "GetSpellTargetLoc", "GetRectCenter", 
    "OffsetLocation", "PolarProjectionBJ", "GetOrderPointLoc", "GetUnitRallyPoint",
    "GetCameraEyePositionLoc", "GetItemLoc", "GetDestructableLoc", "Location",
    "MeleeGetLocWithinRect", "GetPlayerStartLocationLoc", "GetStartLocationLoc",
    "CameraSetupGetDestPositionLoc", "MeleeGetProjectedLoc", "WaygateGetDestinationLocBJ"
]
TIMER_FUNCS = ["CreateTimer"]
TRIGGER_FUNCS = ["CreateTrigger"]
HASHTABLE_FUNCS = ["InitHashtable"]
FORCE_FUNCS = ["CreateForce", "GetPlayersAll", "GetPlayersMatching", "GetPlayersInIsntance"]
RECT_FUNCS = ["Rect", "RectFromCenterSizeBJ"]

ALL_LEAK_TYPES = {
    "location": ("RemoveLocation", LOC_FUNCS),
    "group": ("DestroyGroup", GROUP_FUNCS),
    "timer": ("DestroyTimer", TIMER_FUNCS),
    "trigger": ("DestroyTrigger", TRIGGER_FUNCS),
    "hashtable": ("FlushParentHashtable", HASHTABLE_FUNCS),
    "force": ("DestroyForce", FORCE_FUNCS),
    "rect": ("RemoveRect", RECT_FUNCS)
}

# 这些创建函数返回的句柄通常会被长期持有，自动销毁会破坏地图逻辑
NO_AUTO_DESTROY = {"CreateTrigger", "CreateTimer", "InitHashtable"}
RECT_FUNCS = ["RectFromCenterSizeBJ", "Rect"]
BOOLEXPR_FUNCS = ["Condition", "Filter"]
MATCHING_FUNCS = {"GetUnitsOfPlayerMatching", "GetUnitsInRectMatching", "GetUnitsInRangeOfLocMatching"}

LEAK_CATEGORY = {}
for vtype, (destroyer, creators) in ALL_LEAK_TYPES.items():
    for f in creators:
        LEAK_CATEGORY[f] = (vtype, destroyer)

for f in BOOLEXPR_FUNCS: 
    LEAK_CATEGORY[f] = ("boolexpr", "DestroyBoolExpr")

ALL_FUNCS_SORTED = sorted(LEAK_CATEGORY.keys(), key=len, reverse=True)
CALL_RE = re.compile(r'\b(' + '|'.join(re.escape(f) for f in ALL_FUNCS_SORTED) + r')\(')
SET_RE = re.compile(r'^(\s*set\s+)([A-Za-z_][A-Za-z0-9_]*)(\s*=\s*)(.*)$')
