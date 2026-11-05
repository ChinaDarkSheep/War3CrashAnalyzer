unit wc3props;

{$mode objfpc}{$H+}
{$ASMMODE INTEL}

interface

uses wc3main, wc3collections;

type
	TWc3PropId =
	(
		piContextId = $0,
		piJassEnv = $5,
		piSynData = $D,
		piNetProvider = $E
	);

	TSynDataId =
	(
		sdCheatData = $0,
		sd01 = $1,
		sdNetData = $2,
		sdRandData = $3,
		SYNDATA_WAR3SLKDATABASE_0 = $4,
		SYNDATA_ABILITYDATABASE = $5,
		sdGameWar3 = $6,
		SYNDATA_WAR3SLKDATABASE_1 = $7,
		sd08 = $8,
		SYNDATA_UPGRADEDATABASE = $9,
		sd0A = $A,
		sd0B = $B,
		SYNDATA_UNITCUSTOMDATA = $C,
		SYNDATA_ITEMCUSTOMDATA = $D,
		SYNDATA_DESTRUCTABLECUSTOMDATA = $E,
		sd0F = $F,
		SYNDATA_ABILITYCUSTOMDATA = $10,
		SYNDATA_BUFFCUSTOMDATA = $11,
		SYNDATA_UPGRADECUSTOMDATA = $12,
		sdMiscCustom = $13
	);

	TEngineData = packed record
		MiscProfile: Pointer;
		UnknownProfile: Pointer;
		SynData: specialize TSArray<Pointer>;
	end;
	PEngineData = ^TEngineData;

var
	_GetWc3Prop: function: Pointer; stdcall; // fastcall i

function GetWc3Prop(Index: TWc3PropId): Pointer;
function GetSynData(Index: TSynDataId): Pointer;

implementation

function GetWc3Prop(Index: TWc3PropId): Pointer;
begin
	asm mov ecx,Index end;
	Result:= _GetWc3Prop();
end;

function GetSynData(Index: TSynDataId): Pointer;
var
	EngineData: PEngineData;
begin
	EngineData:= GetWc3Prop(piSynData);
	if EngineData <> nil
		then Result:= EngineData^.SynData[Integer(Index)]
		else Result:= nil;
end;

procedure OnInit;
begin
	PtrUInt(_GetWc3Prop):= GameDll + $4C34D0;
end;

initialization
	wc3main.SubscribeOnInit(@OnInit);
end.

