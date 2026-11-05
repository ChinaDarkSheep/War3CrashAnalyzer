unit wc3netcommands;

{$mode objfpc}{$H+}

interface

uses
	wc3netdata, wc3nettag;

type
	{$PackEnum 1}
	TNetCommandType = (
		ctPause = 1,
		ctUnpause = 2,
		ctGameSpeed = 3,
		ctGameSpeedIncrement = 4,
		ctGameSpeedDecrement = 5,
		ctSave = 6,
		ctSaveDone = 7,
		ctUnitOrderBasic = 16,
		ctUnitOrderTargetPoint = 17,
		ctUnitOrderTargetImage = 18,
		ctUnitOrderTargetImage2 = 19,
		ctUnitOrderTargetImageFogged = 20,
		ctUnitOrderTargetImageFogged2 = 21,
		ctUnitSelectionModify = 22,
		ctUnitDefineControlGroup = 23,
		ctUnitSelectControlGroup = 24,
		ctUnitSelectSubGroup = 25,
		ctUnitRefreshSubGroup = 26,
		ctUnitSelectionEvent = 27,
		ctSelectableSelectionModify = 28,
		ctReviveCancel = 29,
		ctTrainCancel = 30,
		ctCheatCooldown = 32,
		ctCheatCritter = 33,
		ctCheatDefeat = 34,
		ctCheatFastBuild = 35,
		ctCheatFastDeath = 36,
		ctCheatFood = 37,
		ctCheatGod = 38,
		ctCheatGold = 39,
		ctCheatLumber = 40,
		ctCheatMana = 41,
		ctCheatNoDefeat = 42,
		ctCheatNoVictory = 43,
		ctCheatResearch = 44,
		ctCheatResources = 45,
		ctCheatSetTod = 46,
		ctCheatShowMap = 47,
		ctCheatTechTree = 48,
		ctCheatUpgrade = 49,
		ctCheatVictory = 50,
		ctTeamChangeAlliance = 80,
		ctTeamTradeResources = 81,
		ctPlayerChatMatch = 96,
		ctPlayerEndCinematic = 97,
		ctResumeTriggerExec = 98,
		ctTriggerSyncReady = 99,
		ctTrackableHit = 100,
		ctTrackableTrack = 101,
		ctShowSkill = 102,
		ctShowSubmenu = 103,
		ctAllyPing = 104,
		ctDialogButtonClick = 105,
		ctDialogClick = 106,
		ctSyncStoreInteger = 107,
		ctSyncStoreReal = 108,
		ctSyncStoreBoolean = 109,
		ctSyncStoreUnit = 110,
		ctSyncStoreString = 111,
		ctSyncClearInteger = 112,
		ctSyncClearReal = 113,
		ctSyncClearBoolean = 114,
		ctSyncClearUnit = 115,
		ctSyncClearString = 116,
		ctArrowKey = 117,
		ctReplayDataUncompressed = 129,
		ctReplayDataCompressed = 130,
		ctReplayDataDone = 131,
		ctReplayViewSpeedIncrement = 132,
		ctReplayViewSpeedDecrement = 133
	);

	TNetCommandBase = object (TNetEventBase)
		CommandId: TNetCommandType;
		PlayerId: Byte;
	end;
	PNetCommandBase = ^TNetCommandBase;

	TNetCommandPlayerChatMatch = object (TNetCommandBase)
		Message: array [0..255] of Char;
		EventRegistration: TNetTag;
	end;
	PNetCommandPlayerChatMatch = ^TNetCommandPlayerChatMatch;

const
	NET_EVENT_COMMAND_BASE = $A0000;

implementation

end.

