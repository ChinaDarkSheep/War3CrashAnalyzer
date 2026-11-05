unit wc3_game_state;

{$mode objfpc}{$H+}

interface

uses
	wc3collections,
	wc3observer, wc3agent;

type
	TGameVarChangedEvent = object (TEvent)
		NewValue: Single;
	end;

	THandle2AgentReg = record
		References: Dword;
		Value: PAgent;
		AutoDestroy: LongBool;
	end;
	PHandle2AgentReg = ^THandle2AgentReg;

	{ TGameState }

 TGameState = object (TAgentWar3)
	public type
		TEventDataStack = specialize TSGrowableArray<Dword>;

		TAgent2HandleReg = object (specialize TSHashObject<Dword>)
			Handle: Dword;
			BirthTag: Dword;
		end;

		TGameVarEventReg = object (specialize TSHashObject<PChar>)
			Observer: PObserver;
		end;
		PGameVarEventReg = ^TGameVarEventReg;
	public
		field24: Dword;
		Floats: array [0..0] of TFloat;
		field38: Dword;
		Integers: array [0..1] of TInteger;
		Float5C: TFloat;
		field6C: Dword;
		field70: Dword;
		field74: Dword;
		field78: Dword;
		field7C: Dword;
		Integer80: TInteger;
		EventDataArraysCount: Dword;
		EventDataStack: array [0..14] of TEventDataStack;
		FreeHandles: specialize TSGrowableArray<Dword>;
		Handle2AgentRegList: specialize TSGrowableArray<THandle2AgentReg>;
		Agent2HandleTable: specialize TSHashTable<Dword, TAgent2HandleReg, THashlessKeyManager>;
		Func2AgentTable: specialize TSHashTable<Dword, TAgent2HandleReg, THashlessKeyManager>;
		Filter2AgentTable: specialize TSHashTable<Dword, TAgent2HandleReg, THashlessKeyManager>;
		GameVarChangeEventPublishers: specialize TSHashTable<PChar, TGameVarEventReg, TCaseInsensetiveStringHashKeyManager>;
		//GameVarChangedEvent: TGameVarChangedEvent;
		//HastTable_HERONAMESUSED: TSHashTable;
		//UpdateFogTimer_: CAgentTimer;
		//AgentTimer294: CAgentTimer;
		//AgentTimer2A8: CAgentTimer;
		//kQuestManager: Keys;
		//field2C4: DWORD;
		//AggregatedTextTagManager: DWORD;
		//field2CC: DWORD;
		//field2D0: DWORD;
		//field2D4: DWORD;
		//field2D8: DWORD;
		//field2DC: DWORD;
		//field2E0: DWORD;
		//field2E4: DWORD;
		//field2E8: DWORD;
		//field2EC: DWORD;
		//field2F0: DWORD;
		//field2F4: DWORD;
		//field2F8: DWORD;
		//field2FC: DWORD;
		//field300: DWORD;
		//field304: DWORD;
		//field308: DWORD;
		//field30C: DWORD;
		//field310: DWORD;
		//field314: DWORD;
		//field318: DWORD;
		//field31C: DWORD;
		//field320: DWORD;
		//field324: DWORD;
		//field328: DWORD;
		//field32C: DWORD;
		//field330: DWORD;
		//field334: DWORD;
		//field338: DWORD;
		//field33C: DWORD;
		//field340: DWORD;
		//field344: DWORD;
		//field348: DWORD;
		//field34C: DWORD;

	public
		function GetVarChangeEventPublisher(VariableName: PChar): PObserver;
	end;
	PGameState = ^TGameState;

implementation

{ TGameState }

function TGameState.GetVarChangeEventPublisher(VariableName: PChar): PObserver;
var
	Item: PGameVarEventReg;
begin
	Result:= nil;

	if GameVarChangeEventPublishers.Find(VariableName, Item) then begin
		Result:= Item^.Observer;
	end;
end;

end.

