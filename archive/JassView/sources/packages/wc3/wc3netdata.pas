unit wc3netdata;

{$mode objfpc}{$H+}

interface

uses
	wc3observer, wc3collections;

type
	TGameInfo = packed record
		GameName: array [0..31] of Char;
		MaybePassword: array [0..15] of Char;
		EncodedString: array [0..127] of Char;
		PlayerCount: Dword;
		GameType: Dword;
	end;

	TSuspendPlayer = record
		id: Byte;
		StartTime: Dword;
	end;
	PSuspendPlayer = ^TSuspendPlayer;

    TUnknownHashtable = specialize TSHashTable<Pointer, specialize TSHashObject<Pointer>, THashlessKeyManager>;
	TUnknownArray = specialize TSArray<Pointer>;

	TPlayers = record
		Map: TUnknownHashtable;
		GamePlayers: TUnknownArray;
		field34: Dword;
		LobbyPlayers: TUnknownArray;
		field44: Dword;
		Count: Dword;
	end;

	TNetSessionType = (stGame, stReplay);

	TGameState = (
		gsNone,
		gsJoined,
		gsFaked,
		gsLoading,
		gsPlaying,
		gsPausing,
		gsPaused
	);

	TNetEventBase = object (TEvent)
		SessionType: TNetSessionType;
	end;
	PNetEventBase = ^TNetEventBase;

	TNetSession = object
		vtable: Pointer;
		NetEventObserverForCallbacks: TObserver;
		NetEventObserver: TObserver;
		Allocator1C: Dword;
		field20: Dword;
		field24: Dword;
		field28: Dword;
		field2C: Dword;
		field30: Dword;
		Dwords34: array [0..63] of Dword;
		game_info: TGameInfo;
		buffer_field1EC: array [0..129] of BYTE;
		State: TGameState;
		field274: Dword;
		field278: Dword;
		ProcessedCommandsSize: Dword;
		field280: Dword;
		field284: Dword;
		Players: TPlayers;
		LocalPlayerId: Dword;
		field2D8: Dword;
		SaveResult: LongBool;
		SuspendedPlayers: specialize TSArray<TSuspendPlayer>;
		field2EC: Dword;
		field2F0: Dword;
		field2F4: Dword;
		field2F8: Dword;
		GameResult: Pointer;
		field300: Dword;
	end;
	PNetSession = ^TNetSession;

	TNetData = object
		vtable: Pointer;
		field04: Dword;
		Sessions: array [TNetSessionType] of TNetSession;
		// ...
	end;
	PNetData = ^TNetData;

implementation

end.

