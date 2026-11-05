unit jassvm;

{$mode objfpc}{$H+}

interface

uses
	Windows,
	Classes, SysUtils, fgl, Math,
	ArrayList,
	wc3remote, readstring,
	wc3collections, wc3jassvm, wc3props, wc3game, wc3_game_state;

type

	TScriptDataArray = specialize TComparelessArray<TScriptData>;
	TJassStrings = specialize TSArray<TJassString>;
	TInstructions = specialize TComparelessArray<TInstruction>;

	TEventParam =
	(
		epTriggerUnit = $0,
		epTriggerWidget = $1,
		epTriggerTrigger = $2,
		epTriggerPlayer = $3,
		epEventReg = $4,
		epEventData = $5,
		epEventId = $6,
		epFilteringUnit = $7,
		epFilteringPlayer = $8,
		epFilteringDestructable = $9,
		epEnumUnit = $A,
		epEnumPlayer = $B,
		epEnumDestructable = $C,
		epEnumItem = $D,
		epFilteringItem = $E
	);

	TEventParams = array [TEventParam] of TDwordsArray;

	{ TFunction }

	TFunction = class
		Name: String;
		Offset: SizeUInt;
		Size: SizeUInt;
		RetType: TScriptDataType;
	public
		constructor Create;
	end;

	TFunctionsArray = specialize TArray<TFunction>;

	TNativeFunction = class
		Name: String;
		Signature: String;
		Address: Pointer;
	end;

	TNativesArray = specialize TComparelessArray<TNativeFunction>;

	TNativesMap = specialize TFPGMap<String, TNativeFunction>;

	TMyScriptData = record
		DataType: TScriptDataType;
		Initialized: Boolean;
		Value: Dword;
	end;

	TMyScriptDataArray = specialize TComparelessArray<TMyScriptData>;

	TVariables = specialize TFPGMap<String, TMyScriptData>;

	{ TStackFrame }

	TStackFrame = class
	public
		Locals: TVariables;
		Arguments: TVariables;
		Stack: TMyScriptDataArray;
	public
		constructor Create;
		destructor Destroy; override;
	end;

	TStackFrames = specialize TComparelessArray<TStackFrame>;

	TJassScriptsArray = specialize TComparelessArray<TJassScript>;

	TProcess = class;

	{ TThread }

	TThread = class
	public
		Owner: TProcess;
		Handle: Dword;
		Registers: TMyScriptDataArray;
		Frames: TStackFrames;
		Offset: Dword;
	public
		constructor Create;
		destructor Destroy; override;
	end;

	TThreads = specialize TArray<TThread>;

	{ TScript }

	TScript = class
	public
		Handle: Dword;
		Instructions: TInstructions;
		Strings: TStringsArray;
	public
		constructor Create;
	end;

	TScripts = specialize TArray<TScript>;
	TScriptsMap = specialize TFPGMap<Dword, TScript>;

	{ TProcess }

	TProcess = class
	public
		hMainThread: Dword;
		Globals: TVariables;
		Functions: TFunctionsArray;
		Strings: TStringsArray;
		Script: TScript;
		Threads: TThreads;
	public
		constructor Create;
		destructor Destroy; override;
	end;

	TProcesses = specialize TArray<TProcess>;

	{ TJassVM }

	TJassVM = class
	public
		Natives: TNativesMap;
		Scripts: TScriptsMap;
		Processes: TProcesses;
		RunningThreads: TThreads;
	public
		function FindThread(hThread: Dword): TThread;
		constructor Create;
		destructor Destroy; override;
	end;

	EMemoryCorrupted = class (Exception) end;

const
	EventParamReadableName: array [TEventParam] of String =
	(
		'Triggering unit',
		'Triggering widget',
		'Triggering trigger',
		'Triggering player',
		'Event registration',
		'Event data',
		'Event id',
		'Filtering unit',
		'Filtering player',
		'Filtering destructable',
		'Enum unit',
		'Enum player',
		'Enum destructable',
		'Enum item',
		'Filtering item'
	);

function GetArrayOfScriptData(Address: Pointer): TScriptDataArray;

function GetInstancesTable: TPointersArray;
function GetInstances: TPointersArray;
function GetInstance(hInstance: Dword): Pointer;
function GetInstanceRegistersNorm(Instance: Pointer): TMyScriptDataArray;
function GetInstanceId(Instance: Pointer): Integer;
function GetInstanceParentId(Instance: Pointer): Integer;
function IsChildInstance(Instance: Pointer): Boolean;
function GetInstancePosition(Instance: Pointer): Pointer;
function GetInstanceTopmostParentId(Instance: Pointer): Dword;
function GetInstanceStrings(Instance: Pointer): TStringsArray;
function GetInstanceFunctions(Instance: Pointer): TFunctionsArray;
function GetInstanceInitFunctions(Instance: Pointer): TFunctionsArray;
function GetInstanceAllFunctions(Instance: Pointer): TFunctionsArray;
function GetRunningInstances: TPointersArray;
function GetRunningInstancesHandles: TDwordsArray;

function GetScriptInstructions(const Script: TJassScript): TInstructions;
function GetScriptStrings(const Script: TJassScript): TStringsArray;

function GetEventParams: TEventParams;

function GetJassVM: TJassVM;

implementation

procedure ReadWithCheck(Address: Pointer; Buffer: Pointer; Size: SizeUInt);
begin
	if not ReadProcessMemory(WarProcess, Address, Buffer, Size, PDword(nil)^) then
		raise EMemoryCorrupted.CreateFmt('Failed to read data from %P.', [Address]);
end;

//function ChainReadWithCheck(Base: Pointer; Offsets: array of SizeUInt; out Buffer; Count: SizeInt): Boolean;
//begin
	//if not ChainRead(Base, Offsets, Buffer, Count) then
	//	raise EMemoryCorrupted.CreateFmt('Failed to read data from %P.', [Address]);
//end;

function ReadStringWithCheck(Address: PChar): string;
begin
	Result:= readstring.ReadProcessString(WarProcess, Address);
	//raise EMemoryCorrupted.CreateFmt('Failed to read string from %P.', [Address]);
end;

function GetEnvironment: Pointer;
begin
	Result:= wc3remote.GetWc3Prop(piJassEnv);
	if Result = nil then
		raise EMemoryCorrupted.Create('Failed to read environment pointer.');
end;

function GetArrayOfScriptData(Address: Pointer): TScriptDataArray;
var
	Item: Pointer;
	Data: TScriptData;
begin
	Result.Clear;

	for Item in GetLinkedListItems(Address) do begin
		ReadWithCheck(Item, @Data, SizeOf(Data));
		Result.Add(Data);
	end;
end;

//=============

function GetInstancesTable: TPointersArray;
var
	Environment, Item: Pointer;
	List: specialize TSArray<Pointer>;
	i: Integer;
begin
	Result.Clear;

	Environment:= GetEnvironment();
	ReadWithCheck(Environment + $88, @List, SizeOf(List));

	for i:= 0 to List.Length-1 do begin
		ReadWithCheck(List.FItems + i, @Item, SizeOf(Item));

		Result.Add(Item);
	end;
end;

function GetInstances: TPointersArray;
var
	Instance: Pointer;
begin
	Result.Clear;

	for Instance in GetInstancesTable do begin
		if Instance <> nil then Result.Add(Instance);
	end;
end;

function GetInstance(hInstance: Dword): Pointer;
var
	Instances: TPointersArray;
begin
	Instances:= GetInstancesTable();

	if {%H-}InRange(hInstance, 0, Instances.Count - 1) then
		Result:= Instances[hInstance]
	else
		Result:= nil;
end;

function GetInstanceId(Instance: Pointer): Integer;
begin
	ReadWithCheck(Instance + $2850, @Result, SizeOf(Result));
end;

function GetInstanceParentId(Instance: Pointer): Integer;
begin
	ReadWithCheck(Instance + $2854, @Result, SizeOf(Result));
end;

function IsChildInstance(Instance: Pointer): Boolean;
var
	IsChild: LongBool;
begin
	ReadWithCheck(Instance + $18, @IsChild, SizeOf(IsChild));

	Result:= IsChild;
end;

function GetInstancePosition(Instance: Pointer): Pointer;
begin
	ReadWithCheck(Instance + $20, @Result, SizeOf(Result));
end;

procedure GetInstanceScript(Instance: Pointer; out Script: TJassScript);
var
	pScript: Pointer;
begin
	ReadWithCheck(Instance + $2858, @pScript, SizeOf(pScript));
	ReadWithCheck(pScript, @Script, SizeOf(Script));
end;

function GetInstanceScriptHandle(Instance: Pointer): Dword;
type
	TScript2HandleReg = record
		Script: Pointer;
		field04: Dword;
		field08: Dword;
		field0C: Dword;
		field10: Dword;
		field14: Dword;
		Handle: Dword;
	end;

var
	Environment, Item, pScript: Pointer;
	Data: TScript2HandleReg;
begin
	Result:= 0;

	Environment:= GetEnvironment();

	ReadWithCheck(Instance + $2858, @pScript, SizeOf(pScript));

	for Item in GetLinkedListItems(Environment + $60 + $04) do begin
		ReadWithCheck(Item, @Data, SizeOf(Data));

		if Data.Script = pScript then begin
			Result:= Data.Handle;
			break;
		end;
	end;
end;

function GetInstanceTopmostParentId(Instance: Pointer): Dword;
begin
	while IsChildInstance(Instance) do begin
		Instance:= GetInstance(GetInstanceParentId(Instance));
	end;

	Result:= GetInstanceId(Instance);
end;

function GetInstanceStrings(Instance: Pointer): TStringsArray;
var
	pJassStrings: Pointer;
	JassStrings: TJassStrings;
	Items: array of TJassString;
	i: Integer;
begin
	Result.Clear;

	ReadWithCheck(Instance + $2874, @pJassStrings, SizeOf(pJassStrings));
	ReadWithCheck(pJassStrings, @JassStrings, SizeOf(JassStrings));

	SetLength(Items, JassStrings.Length);
	ReadWithCheck(JassStrings.FItems, @Items[0], Length(Items) * SizeOf(TJassString));

	Result.Count:= Length(Items);

	for i:= 0 to High(Items) do begin
		Result[i]:= GetStringValue(Items[i].FValue);
	end;
end;

function GetInstanceFunctions(Instance: Pointer): TFunctionsArray;
var
	Script: TJassScript;
	Map, Item: Pointer;
	Data: TFuncAddr;
	f: TFunction;
begin
	Result.Init;

	GetInstanceScript(Instance, Script);
	ReadWithCheck(Instance + $2884, @Map, SizeOf(Map));

	for Item in GetLinkedListItems(Map + $04) do begin
		ReadWithCheck(Item, @Data, SizeOf(Data));

		f:= TFunction.Create;
		f.Name:= ReadStringWithCheck(Data.HashKeyData.Key);
		f.Offset:= SizeUInt(Data.Address - Pointer(Script.Code));
		f.RetType:= TScriptDataType(Data.RetType);

		Result.Add(f);
	end;
end;

function GetInstanceInitFunctions(Instance: Pointer): TFunctionsArray;
var
	Script: TJassScript;
	pList, Item: Pointer;
	InitFunc: TInitFuncAddr;
	f: TFunction;
begin
	Result.Init;

	GetInstanceScript(Instance, Script);
	ReadWithCheck(Instance + $2880, @pList, SizeOf(pList));

	for Item in GetLinkedListItems(pList) do begin
		ReadWithCheck(Item, @InitFunc, SizeOf(InitFunc));

		f:= TFunction.Create;
		f.Name:= Format('<init> #%d', [Result.Count + 1]);
		f.Offset:= SizeUInt(InitFunc.Address - Pointer(Script.Code));
		f.RetType:= stVoid;

		Result.Add(f);
	end;
end;

function GetInstanceAllFunctions(Instance: Pointer): TFunctionsArray;
begin
	Result.Init;
	Result.AddAll( GetInstanceFunctions(Instance) );
	Result.AddAll( GetInstanceInitFunctions(Instance) );
end;

procedure FindFunctionSize(f: TFunction; Instructions: TInstructions);
var
	StartIndex, Position: Integer;
	Founded: Boolean;
begin
	StartIndex:= f.Offset div SizeOf(TInstruction);
	Position:= StartIndex;

	Founded:= False;
	while Position < Instructions.Count do begin
		if TOperationCode(Instructions[Position].id) = opEndFunction then begin
			Founded:= True;
			break;
		end;

		Inc(Position);
	end;

	if Founded then
		f.Size:= (Position - StartIndex) * SizeOf(TInstruction)
	else
		raise Exception.CreateFmt('Can''t find function end: "%s".', [f.Name]);
end;

procedure FindFunctionsSizes(Instance: Pointer; Functions: TFunctionsArray);
var
	Script: TJassScript;
	Instructions: TInstructions;
	f: TFunction;
begin
	GetInstanceScript(Instance, Script);
	Instructions:= GetScriptInstructions(Script);

	for f in Functions do begin
		FindFunctionSize(f, Instructions);
	end;
end;

function GetRunningInstances: TPointersArray;
var
	JassVM, Items, Instance: Pointer;
	Count, i: Integer;
begin
	Result.Clear;

	JassVM:= GetEnvironment();
	ReadWithCheck(JassVM + $0C, @Items, SizeOf(Items));
	ReadWithCheck(JassVM + $14, @Count, SizeOf(Count));

	for i:= 0 to Count-1 do begin
		ReadWithCheck(Items + SizeOf(Pointer) * i, @Instance, SizeOf(Instance));
		Result.Add(Instance);
	end;
end;

function GetRunningInstancesHandles: TDwordsArray;
var
	Instance: Pointer;
begin
	Result.Clear;

	for Instance in GetRunningInstances do begin
		Result.Add(GetInstanceId(Instance));
	end;
end;

// ========================

function GetScriptInstructions(const Script: TJassScript): TInstructions;
begin
	Result.Count:= Script.CodeSize div SizeOf(TInstruction);
	ReadWithCheck(Script.Code, @Result.FItems[0], Result.Count * SizeOf(TInstruction));
end;

function GetScriptStrings(const Script: TJassScript): TStringsArray;
var
	Table: THashedStringTable;
	Items: TPointersArray;
	_Array: TPointersArray.TItems;
	i: Integer;
	HashedString: THashedString;
begin
	Result.Clear;

	ReadWithCheck(Script.Strings, @Table, SizeOf(Table));
	Items.Count:= Table.FItems.Length;

	_Array:= Items.GetItems();
	ReadWithCheck(Table.FItems.FItems, @_Array[0], Items.Count * SizeOf(Pointer));

	Result.Count:= Items.Count;

	for i:= 0 to Items.Count - 1 do begin
		if Items[i] <> nil then begin
			ReadWithCheck(Items[i], @HashedString, SizeOf(HashedString));
			Result[i]:= ReadStringWithCheck(HashedString.HashKeyData.Key);
		end
		else
			Result[i]:= '<null>';
	end;
end;

// ========================

function GetNatives: TNativesArray;
var
	Natives, Item: Pointer;
	Data: TNativeFunc;
	Native: TNativeFunction;
begin
	Result.Clear;

	Natives:= GetEnvironment() + $18;

	for Item in GetLinkedListItems(Natives + $04) do begin
		ReadWithCheck(Item, @Data, SizeOf(Data));

		Native:= TNativeFunction.Create;

		Native.Name:= ReadStringWithCheck(Data.HashKeyData.Key);
		Native.Signature:= ReadStringWithCheck(Data.Signature);
		Native.Address:= Data.Address;

		Result.Add(Native);
	end;
end;

procedure FillMapWithNatives(Map: TNativesMap);
var
	Native: TNativeFunction;
begin
	for Native in GetNatives() do begin
		Map[Native.Name]:= Native;
	end;
end;

// ========================

function ConvertVariable(const Data: TScriptData): TMyScriptData;
begin
	//Result.Name:= ReadStringWithCheck(Data.HashObject.Key);
	Result.DataType:= Data._Type;
	Result.Initialized:= Data.InitializedType <> stVoid;
	//Result.IsArgument:= Data.IsArgument;
	Result.Value:= Data.Value;
end;

function GetFrameStack(const Frame: TFrame): TMyScriptDataArray;
var
	Data: TScriptData;
	i: Integer;
begin
	Result.Init;

	for i:= 0 to Frame.Stack.Length - 1 do begin
		ReadWithCheck(Frame.Stack.Items[i], @Data, SizeOf(Data));

		Result.Add(ConvertVariable(Data));
	end;
end;

function ConvertFrame(const Frame: TFrame): TStackFrame;
var
	pData: Pointer;
	Data: TScriptData;
	MyData: TMyScriptData;
	Name: String;
begin
	Result:= TStackFrame.Create;

	for pData in GetLinkedListItems(TPtrLinkedList(Frame.Locals.Items)) do begin
		ReadWithCheck(pData, @Data, SizeOf(Data));

		Name:= ReadStringWithCheck(Data.HashKeyData.Key);
		MyData:= ConvertVariable(Data);

		if not Data.IsArgument then
			Result.Locals[Name]:= MyData
		else
			Result.Arguments[Name]:= MyData;
	end;

	Result.Stack:= GetFrameStack(Frame);
end;

function GetInstanceRegistersNorm(Instance: Pointer): TMyScriptDataArray;
var
	Registers: array [0..255] of TScriptData;
	i: Integer;
begin
	Result.Clear;
	ReadWithCheck(Instance + $50, @Registers, SizeOf(Registers));

	Result.Count:= Length(Registers);

	for i:= 0 to High(Registers) do begin
		Result[i]:= ConvertVariable(Registers[i]);
	end;
end;

procedure GetInstanceGlobals(Instance: Pointer; Variables: TVariables);
var
	pGlobals: Pointer;
	Globals: TScriptDataArray;
	Data: TScriptData;
	MyData: TMyScriptData;
	Name: String;
begin
	ReadWithCheck(Instance + $285C, @pGlobals, SizeOf(pGlobals));

	Globals:= GetArrayOfScriptData(pGlobals + $04);

	for Data in Globals do begin
		Name:= ReadStringWithCheck(Data.HashKeyData.Key);
		MyData:= ConvertVariable(Data);

		Variables[Name]:= MyData;
	end;
end;

function GetInstanceFrames(Instance: Pointer): TStackFrames;
var
	pFrame: Pointer;
	Frame: TFrame;
begin
	Result.Init;

	for pFrame in GetLinkedListItems(Instance + $2860) do begin
		ReadWithCheck(pFrame, @Frame, SizeOf(Frame));

		Result.Add(ConvertFrame(Frame));
		if Frame.IsFirstFrame then break;
	end;

	Result.InvertOrder;
end;

function ConvertInstance(Instance: Pointer): TThread;
var
	Script: TJassScript;
begin
	Result:= TThread.Create;

	GetInstanceScript(Instance, Script);

	Result.Handle:= GetInstanceId(Instance);
	Result.Registers:= GetInstanceRegistersNorm(Instance);
	Result.Frames:= GetInstanceFrames(Instance);
	Result.Offset:= GetInstancePosition(Instance) - Pointer(Script.Code);
end;

function ConvertScript(const Script: TJassScript): TScript;
begin
	Result:= TScript.Create;
	Result.Instructions:= GetScriptInstructions(Script);
	Result.Strings:= GetScriptStrings(Script);
end;

type
	TProcessesMap = specialize TFPGMap<Dword, TProcess>;

function FunctionComparator(const A, B): Integer; cdecl;
var
	FunctionA: TFunction absolute A;
	FunctionB: TFunction absolute B;
begin
	Result:= FunctionA.Offset - FunctionB.Offset;
end;

function GetProcesses: TProcesses;
var
	Map: TProcessesMap;
	Instance: Pointer;
	Process: TProcess;
	Thread: TThread;
begin
	Result.Clear;
	Map:= TProcessesMap.Create;

	for Instance in GetInstances() do begin
		if IsChildInstance(Instance) then continue;

		Process:= TProcess.Create;

		Process.hMainThread:= GetInstanceId(Instance);
		Process.Strings:= GetInstanceStrings(Instance);
		GetInstanceGlobals(Instance, Process.Globals);
		Process.Functions:= GetInstanceAllFunctions(Instance);
		Process.Functions.Sort(@FunctionComparator);
		FindFunctionsSizes(Instance, Process.Functions);

		Map[Process.hMainThread]:= Process;
		Result.Add(Process);
	end;

	for Instance in GetInstances() do begin
		Process:= Map[GetInstanceTopmostParentId(Instance)];
		Thread:= ConvertInstance(Instance);
		Thread.Owner:= Process;
		Process.Threads.Add(Thread);
	end;

	Map.Destroy;
end;

function GetScripts: TScriptsMap;
var
	Environment, Item: Pointer;
	List: specialize TSArray<Pointer>;
	i: Integer;
	Script: TJassScript;
	MyScript: TScript;
begin
	Result:= TScriptsMap.Create;

	Environment:= GetEnvironment();
	ReadWithCheck(Environment + $40, @List, SizeOf(List));

	for i:= 0 to List.Length - 1 do begin
		ReadWithCheck(List.FItems + i, @Item, SizeOf(Item));
		if Item = nil then continue;
		ReadWithCheck(Item, @Script, SizeOf(Script));
		MyScript:= ConvertScript(Script);
		MyScript.Handle:= i;
		Result[i]:= MyScript;
	end;
end;

function GetGameWar3: PGameWar3;
begin
	ReadWithCheck(g_GameWar3, @Result, SizeOf(Result));
end;

function GetGameStateObject: PGameState;
var
	game: PGameWar3;
begin
	game:= GetGameWar3();
	if game <> nil
		then ReadWithCheck(PByte(game) + $1C, @Result, SizeOf(Result))
		else Result:= nil;
end;

procedure ClearEventParams(out Params: TEventParams);
var
	i: TEventParam;
begin
	for i in TEventParam do begin
		Params[i].Init;
	end;
end;

function GetEventParams: TEventParams;
var
	Arrays: array [TEventParam] of specialize TSGrowableArray<Pointer>;
	i: TEventParam;
	items: TDwordsArray.TItems;
	game_state: PGameState;
begin
	ClearEventParams(Result);

	game_state:= GetGameStateObject();
	if game_state <> nil then begin
		ReadWithCheck(PByte(game_state) + $94, @Arrays, SizeOf(Arrays));

		for i in TEventParam do begin
			Result[i].Count:= Arrays[i].Length;
			items:= Result[i].GetItems();
			ReadWithCheck(Arrays[i].FItems, @items[0], Length(items) * SizeOf(Dword));
		end;
	end;
end;

function GetJassVM: TJassVM;
var
	Process: TProcess;
	hScript, hThread: Dword;
begin
	Result:= TJassVM.Create;

	FillMapWithNatives(Result.Natives);
	Result.Scripts:= GetScripts;
	Result.Processes:= GetProcesses;

	for Process in Result.Processes do begin
		hScript:= GetInstanceScriptHandle(GetInstance(Process.hMainThread));
		Process.Script:= Result.Scripts[hScript];
	end;

	for hThread in GetRunningInstancesHandles() do begin
		Result.RunningThreads.Add(Result.FindThread(hThread));
	end;
end;

{ TFunction }

constructor TFunction.Create;
begin
	Name:= '';
end;

{ TStackFrame }

constructor TStackFrame.Create;
begin
	Locals:= TVariables.Create;
	Arguments:= TVariables.Create;
	Stack.Clear;
end;

destructor TStackFrame.Destroy;
begin
	Locals.Destroy;
	Arguments.Destroy;
end;

{ TThread }

constructor TThread.Create;
begin
	Owner:= nil;
	Registers.Clear;
	Frames.Clear;
end;

destructor TThread.Destroy;
begin

end;

{ TScript }

constructor TScript.Create;
begin
	Instructions.Clear;
	Strings.Clear;
end;

{ TProcess }

constructor TProcess.Create;
begin
	hMainThread:= 0;
	Globals:= TVariables.Create;
	Functions.Clear;
	Strings.Clear;
	Threads.Clear;
end;

destructor TProcess.Destroy;
begin
	Globals.Destroy;
end;

{ TJassVM }

function TJassVM.FindThread(hThread: Dword): TThread;
var
	Process: TProcess;
	Thread: TThread;
begin
	for Process in Processes do begin
		for Thread in Process.Threads do begin
			if Thread.Handle = hThread then begin
				Result:= Thread;
				exit;
			end;
		end;
	end;

	Result:= nil;
end;

constructor TJassVM.Create;
begin
	Natives:= TNativesMap.Create;
	Scripts:= TScriptsMap.Create;
	Processes.Clear;
	RunningThreads.Clear;
end;

destructor TJassVM.Destroy;
//var
	//Process: TProcess;
begin
	Natives.Destroy;
	Scripts.Destroy;

	//for Process in Processes do
	//	Process.Destroy;
end;

end.















