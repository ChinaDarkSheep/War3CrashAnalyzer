unit wc3remote;

{$mode ObjFPC}{$H+}

interface

uses
	Windows,
	ArrayList,
	wc3props, wc3string, wc3collections,
	readstring, errors, modulesutil;

type
	TPointersArray = specialize TArray<Pointer>;
	TPtrLinkedList = specialize TSLinkedList<Pointer, TMissingInitialOffset>;

function Read(Address: Pointer; Buffer: Pointer; Size: Dword): Boolean;
function Write(Address: Pointer; Buffer: Pointer; Size: Dword): Boolean;

function GetLinkedListItems(const List: TPtrLinkedList): TPointersArray;
function GetLinkedListItems(Address: Pointer): TPointersArray;

function ChainRead(Offsets: array of SizeUInt; out Buffer; Count: SizeInt): Boolean;
function GetStringValue(const rcString: TRCString): String;

function GetWc3Prop(Id: TWc3PropId): Pointer;
function GetSynData(Id: TSynDataId): Pointer;

procedure open_game_process(ProcessId: Dword);
procedure close_game_process;

var
	//WarWindow: HWND;
	WarProcessId: Dword = Dword(-1);
	//WarThreadId: Dword;
	WarProcess: Handle = INVALID_HANDLE_VALUE;
	WarGameBase: Pointer = nil;

	g_Wc3Props: Pointer;
	g_GameWar3: Pointer;

implementation

uses SysUtils;

function Read(Address: Pointer; Buffer: Pointer; Size: Dword): Boolean;
begin
	Result:= ReadProcessMemory(WarProcess, Address, Buffer, Size, nil);
end;

function Write(Address: Pointer; Buffer: Pointer; Size: Dword): Boolean;
begin
	Result:= WriteProcessMemory(WarProcess, Address, Buffer, Size, nil);
end;

function GetLinkedListItems(const List: TPtrLinkedList): TPointersArray;
var
	Node: TPtrLinkedList.TNode;
begin
	Result.Clear;
	Node:= List.FRoot;

	while {%H-}PtrInt(Node.Value) > 0 do begin
		Result.Add(Node.Value);
		if not Read(Pointer(Node.Value) + List.FOffset, @Node, SizeOf(Node))
			then break;
	end;
end;

function GetLinkedListItems(Address: Pointer): TPointersArray;
var
	List: TPtrLinkedList;
begin
	Result.Clear;
	if not Read(Address, @List, SizeOf(List)) then exit;
	Result:= GetLinkedListItems(List);
end;

function ChainRead(Offsets: array of SizeUInt; out Buffer; Count: SizeInt): Boolean;
var
	i: Integer;
	CurAddr,TempAddr: Pointer;
begin
	Result:= false;

	CurAddr:= Pointer(Offsets[0]);
	for i:= 1 to High(Offsets) do begin
		if Read(CurAddr, @TempAddr, SizeOf(TempAddr)) = false
			then Exit;
		CurAddr:= TempAddr;
		CurAddr:= CurAddr + Offsets[i];
	end;

	Result:= Read(CurAddr, @Buffer, Count);
end;

function GetStringValue(const rcString: TRCString): String;
var
	Repr: TStringRep;
begin
	Result:= '<error>';

	if not Read(rcString.Representation, @Repr, SizeOf(Repr)) then exit;

	if Repr.HashKeyData.Key = nil
		then Result:= '<null string>'
		else Result:= ReadProcessString(WarProcess, Repr.HashKeyData.Key);
end;

// OTHER

function GetWc3Prop(Id: TWc3PropId): Pointer;
var
	CHAIN_WC3PROPS: TDwordsArray;
begin
	Result:= nil;
	CHAIN_WC3PROPS.Clear;
	CHAIN_WC3PROPS.AddAll([Dword(g_Wc3Props), SizeOf(Pointer) * Integer(Id)]);
	ChainRead(CHAIN_WC3PROPS.GetItems, Result, SizeOf(Result));
end;

function GetSynData(Id: TSynDataId): Pointer;
var
	CHAIN_SYNDATA: TDwordsArray;
begin
	Result:= nil;
	CHAIN_SYNDATA.Clear;
	CHAIN_SYNDATA.AddAll([Dword(GetWc3Prop(piSynData)), SizeOf(Pointer) * Integer(Id)]);
	ChainRead(CHAIN_SYNDATA.GetItems, Result, SizeOf(Result));
end;

procedure open_game_process(ProcessId: Dword);
var
	Process: Handle;
	GameBase: Pointer;
begin
	GameBase:= GetModule(ProcessId, 'game.dll').modBaseAddr;

	Process:= OpenProcess(
		PROCESS_VM_READ or PROCESS_QUERY_LIMITED_INFORMATION,
		False,
		ProcessId
	);
	if Process = INVALID_HANDLE_VALUE
		then RaiseLastOSError('Failed to open process %d.', [Qword(ProcessId)]);

    close_game_process();

	WarProcessId:= ProcessId;
	WarProcess:= Process;
	WarGameBase:= GameBase;

	g_Wc3Props:= WarGameBase + $ADA848;
	g_GameWar3:= WarGameBase + $AB65F4;
end;

procedure close_game_process;
begin
	WarProcessId:= Dword(-1);
	if WarProcess <> INVALID_HANDLE_VALUE
		then CloseHandle(WarProcess);
	WarProcess:= INVALID_HANDLE_VALUE;
	WarGameBase:= nil;
end;

end.

