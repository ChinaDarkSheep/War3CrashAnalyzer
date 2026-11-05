unit wc3player;

{$mode objfpc}{$H+}

interface

uses
	wc3collections, wc3string, wc3agent;

type
	TPlayerController = (
		pcUser,
		pcComputer,
		pcRescuable,
		pcNeutral,
		pcCreep,
		pcNone
	);

	TPlayerWar3 = object (TAgentWar3)
		Name: TRCString;
		Index: Byte;
		Selection: Pointer; // PSelectionWar3
		Alliances: Pointer; // PAlliances
		IntegersCount: Dword;
		Integers: array [0..25] of TInteger;
		field1E0: Dword;
		GoldTaxRates: Dword;
		field1E8: Dword;
		field1EC: Dword;
		field1F0: Dword;
		field1F4: Dword;
		field1F8: Dword;
		field1FC: Dword;
		field200: Dword;
		field204: Dword;
		field208: Dword;
		SelectedUnits__: Dword;
		field210: Dword;
		field214: Dword;
		LumberTaxRates: Dword;
		field21C: Dword;
		field220: Dword;
		field224: Dword;
		field228: Dword;
		field22C: Dword;
		field230: Dword;
		field234: Dword;
		field238: Dword;
		field23C: Dword;
		field240: Dword;
		field244: Dword;
		field248: Dword;
		field24C: Dword;
		field250: Dword;
		field254: Dword;
		field258: Dword;
		RacePreference: Dword;
		field260: Dword;
		ColorIndex: Dword;
		Controller: TPlayerController;
		Difficulty: Dword;
		SlotState: Dword;
		StartLocIndex: Dword;
		TeamId: Dword;
		field27C: Dword;
		field280: Dword;
		field284: Dword;
		field288: Dword;
		field28C: Dword;
		field290: Dword;
		field294: Dword;
		FloatMini1_vtable: Pointer;
		FloatMini1_value: Single;
		FloatMini2_vtable: Dword;
		FloatMini2_value: Single;
		IsReferee: LongBool;
		UnitArray7: specialize TSGrowableArray<Pointer>; // PUnit
		IntegerMiniArray7: Dword;
		field2C0: Dword;
		field2C4: Dword;
		field2C8: Dword;
		field2CC: Dword;
		TechTree: Pointer;
		field2D4_key1_: Dword;
		field2D8_key2_: Dword;
		field2DC: Dword;
		field2E0: Dword;
		field2E4: Dword;
		field2E8: Dword;
		field2EC: Dword;
		field2F0_key1_: Dword;
		field2F4_key2_: Dword;
		field2F8: Dword;
		AgentTimer2FC: Dword;
		field300: Dword;
		field304: Dword;
		field308: Dword;
		field30C: Dword;
		rcstring310: Dword;
		field314: Dword;
		field318: Dword;
		field31C: Dword;
		field320: Dword;
		field324: Dword;
		field328: Dword;
		field32C: Dword;
		field330: Dword;
		field334: Dword;
	end;
	PPlayerWar3 = ^TPlayerWar3;

implementation

end.

