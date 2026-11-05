unit wc3game;

{$mode objfpc}{$H+}

interface

uses
	wc3main,
	wc3collections, wc3agent, wc3_game_state, wc3player,
	wc3jassvm;

type

	{ TGameWar3 }

	TGameWar3 = object
	private type
		PGameWar3 = ^TGameWar3;
	public
		vtable: Pointer;
		hMainScript: TScriptHandle;
		hMainInstance: TInstanceHandle;
		Executions: specialize TSGrowableArray<Pointer>;
		State: PGameState;
		Orders: Pointer;
		GameBuild: Dword;
		LocalPlayerId: Word;
		ReplayPlayerId: Word;
		field2C: Dword;
		MapSetup: Pointer;
		FogOfWarMap: Pointer;
		jstr_field38: DWORD;
		field3C: DWORD;
		field40: DWORD;
		field44: DWORD;
		PlayersCount: DWORD;
		field4C: DWORD;
		field50: DWORD;
		field54: DWORD;
		Players: array [0..15] of PPlayerWar3;
		// ...
	private
		class function GetInstance: PGameWar3; static;
	public
		class property Instance: PGameWar3 read GetInstance;
	end;
	PGameWar3 = ^TGameWar3;

	TJassFunc = object (TAgentWar3)
		hCode: TJassFunctionHandle;
	end;
	PJassFunc = ^TJassFunc;

var
	ppGameWar3: ^PGameWar3;

implementation

procedure Init;
begin
	ppGameWar3:= Pointer(GameDll+$AB65F4);
end;

{ TGameWar3 }

class function TGameWar3.GetInstance: PGameWar3;
begin
	Result:= ppGameWar3^;
end;

initialization
	wc3main.SubscribeOnInit(@Init)

end.

