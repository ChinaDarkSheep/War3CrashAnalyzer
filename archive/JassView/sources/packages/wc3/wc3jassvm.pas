unit wc3jassvm;

{$mode objfpc}{$H+}

interface

uses
	wc3main, wc3memory, wc3string, wc3collections, wc3props;

type
	TScriptExitCode = (
		scExecutionCompleted = 1,
		scOpLimitReached = 2,
		scSleeping = 3,
		scSyncing = 4,
		scFunctionNotFound = 5,
		scOverflowOrUndefined = 6,
		scZeroDivision = 7
	);

const
	SCRIPT_TYPE_LETTER_VOID = 'V';
	SCRIPT_TYPE_LETTER_CODE = 'C';
	SCRIPT_TYPE_LETTER_INTEGER = 'I';
	SCRIPT_TYPE_LETTER_REAL = 'R';
	SCRIPT_TYPE_LETTER_STRING = 'S';
	SCRIPT_TYPE_LETTER_HANDLE = 'H';
	SCRIPT_TYPE_LETTER_BOOLEAN = 'B';

type
	TScriptDataType =
	(
		stVoid = $00,
		stRetAddr = $01,
		stNull = $02,
		stCode = $03,

		stInteger = $04,
		stReal = $05,
		stString = $06,
		stHandle = $07,
		stBoolean = $08,

		stArrayOfInteger = $09,
		stArrayOfReal = $0A,
		stArrayOfString = $0B,
		stArrayOfHandle = $0C,
		stArrayOfBoolean = $0D
	);

	TOperationCode =
	(
		opEndProgram   = $01,
		opDebug        = $02,
		opFunction     = $03,
		opEndFunction  = $04,
		opLocal        = $05,
		opGlobal       = $06,
		opConstant     = $07,
		opArgument     = $08,
		opParentType   = $09,
		opChildType    = $0A,
		opCleanStack   = $0B,
		opLiteral      = $0C,
		opMove         = $0D,
		opGetVar       = $0E,
		opGetCode      = $0F,
		opGetArray     = $10,
		opSetVar       = $11,
		opSetArray     = $12,
		opPush         = $13,
		opPop          = $14,
		opNativeCall   = $15,
		opCall         = $16,
		opI2R          = $17,
		opAnd          = $18,
		opOr           = $19,
		opEqual        = $1A,
		opNotEqual     = $1B,
		opLesserEqual  = $1C,
		opGreaterEqual = $1D,
		opLesser       = $1E,
		opGreater      = $1F,
		opAdd          = $20,
		opSub          = $21,
		opMul          = $22,
		opDiv          = $23,
		opModulo       = $24,
		opNegate       = $25,
		opNot          = $26,
		opReturn       = $27,
		opLabel        = $28,
		opJumpIfTrue   = $29,
		opJumpIfFalse  = $2A,
		opJump         = $2B
	);

	// functions

	TNativeFunc = object
		vtable: Pointer;
		HashKeyData: specialize THashKeyData<PChar>;
		// field04: Dword;
		// field08: Dword;
		// field0C: Dword;
		// field10: Dword;
		// field14: Dword;
		// Name: PChar;
		Address: Pointer;
		ArgsCount: Dword;
		Signature: PChar;
		field28: Dword;
		field2C: Dword;
		field30: Dword;
		field34: Dword;
		rettype: TScriptDataType;
	end;
	PNativeFunc = ^TNativeFunc;

	TFuncAddr = object (specialize TSHashObject<PChar>)
		// Hash: Dword;
		// field04: Dword;
		// field08: Dword;
		// field0C: Dword;
		// field10: Dword;
		// Name: PChar;
		Address: Pointer;
		RetType: Dword;
	end;
	PFuncAddr = ^TFuncAddr;

	PInitFuncAddr = ^TInitFuncAddr;
	TInitFuncAddr = record
		Node: specialize TSLinkedNode<PInitFuncAddr>;
		Address: Pointer;
	end;

	// script

	TInstruction = packed record
		r3, r2, r1, id: Byte;
		Parameter: Dword;
	end;
	PInstruction = ^TInstruction;

	THashedString = object (specialize TSHashObject<PChar>)
		Index: Dword;
	end;
	PHashedString = ^THashedString;

	THashedStrings = specialize TSGrowableArray<PHashedString>;
	PHashedStrings = ^THashedStrings;

	{ THashedStringTable }

	THashedStringTable = object
	public
		FItems: THashedStrings;
		FStrToItem: specialize TSHashTable<PChar, THashedString, TStringHashKeyManager>;
	private
		function GetItem(AIndex: Dword): PChar;
		function GetItemHash(AIndex: Dword): Dword;
		function GetLength: Dword;
	public
		function GetItemIndex(AItem: PChar; out AIndex: Dword): Boolean;
	public
		property Items[AIndex: Dword]: PChar read GetItem; default;
		property ItemHashes[AIndex: Dword]: Dword read GetItemHash;
		property Length: Dword read GetLength;
	end;
	PHashedStringTable = ^THashedStringTable;

	TJassScript = record
		Code: PInstruction;
		CodeSize: SizeUInt;
		Strings: PHashedStringTable;
		RiskLevel: Dword;
	end;
	PJassScript = ^TJassScript;

	// data

	{ TJassArray }

	TJassArray = object
		vtable: Pointer;
		List: specialize TSGrowableArray<Dword>;
	public
		{constructor} procedure Init;
		{destructor} procedure Done;
	end;
	PJassArray = ^TJassArray;

	{ TJassString }

	TJassString = object
	public
		FValue: TRCString;
		FReferences: Dword;
	private
		procedure SetContent(AContent: PChar);
		function GetContent: PChar;
	public
		property Content: PChar read GetContent write SetContent;
	public
		{constructor} procedure Init;
		{destructor} procedure Done;
	end;
	PJassString = ^TJassString;

	TJassObjectHandle = Dword;
	TJassStringHandle = Dword;

	// hz
	TJassHandle = specialize TSHashObject<PChar>;

	{ TScriptData }

	TScriptData = object (specialize TSHashObject<PChar>)
		InitializedType: TScriptDataType;
		_Type: TScriptDataType;
		Value: Dword;
		IsArgument: LongBool;
	public
		{constructor} procedure Init;
		{destructor} procedure Done;
	end;
	PScriptData = ^TScriptData;

	{ TFrameStackEnumerator }

	PFrameStack = ^TFrameStack;

	TFrameStackEnumerator = object
	private
		FOwner: PFrameStack;
		FPosition: Dword;
	public
		function MoveNext: Boolean;
		function GetCurrent: PScriptData;
		procedure Reset;
		property Current: PScriptData read GetCurrent;
	public
		constructor Init(AOwner: PFrameStack);
	end;

	TFrameStack = object
		Capacity: Dword;
		Items: array [0..31] of PScriptData;
		Length: Dword;
	public
		{constructor} procedure Init;
		{destructor} procedure Done;
		function GetEnumerator: TFrameStackEnumerator;
	end;

	PFrame = ^TFrame;

	{ TFrame }

	TFrame = object
		Node: specialize TSLinkedNode<PFrame>;
		Stack: TFrameStack;
		Locals: specialize TSHashTable<PChar, TScriptData, TConstantStringHashKeyManager>;
		IsFirstFrame: LongBool;
	public
		{constructor} procedure Init;
		{destructor} procedure Done;
	end;

	// instance

	TJassFunctionHandle = Dword;
	TRCStringNode = specialize TSHashNode<PInstruction, TRCString>;

	//TInstanceHandleTableItemManager = object
	//	class procedure InitilizeItem(var AItem: TItem; const AKey: TKey); static;
	//end;

	{ TDefaultInstanceHandleTableItemManager }

	generic TDefaultInstanceHandleTableItemManager<T> = object
		procedure SetupItem(var AItem: T; const AKey: T); static;
		function ExtractItemKey(var AItem: T): T; static;
		procedure ClearItem(var {%H-}AItem: T); static;
	end;

	{ TJassStringInstanceHandleTableItemManager }

	TJassStringInstanceHandleTableItemManager = object
		procedure SetupItem(var AItem: TJassString; const AKey: PChar); static;
		function ExtractItemKey(var AItem: TJassString): PChar; static;
		procedure ClearItem(var AItem: TJassString); static;
	end;

	{ TInstanceHandleTable }

	generic TInstanceHandleTable<TItem, TItemManager, TItemArrayManager, TKey, THashKeyManager> = object
	type
		PItem = ^TItem;
		TItems = specialize TSGrowableArrayM<TItem, TItemArrayManager>;
		PItems = ^TItems;
		TItemHandle = Dword;
		TItemHandles = specialize TSGrowableArray<TItemHandle>;
		PItemHandles = ^TItemHandles;
		TItemHandleNode = specialize TSHashNode<TKey, TItemHandle>;
		PItemHandleNode = ^TItemHandleNode;
		THandleByKeyTable = specialize TSHashTable<TKey, TItemHandleNode, THashKeyManager>;
		PHandleByKeyTable = ^THandleByKeyTable;
	public // Temp for debug
		FItems: PItems;
		FFreeHandles: PItemHandles;
		FHandleByKeyTable: PHandleByKeyTable;
	private
		function GetItem(AIndex: TItemHandle): TItem;
		function GetItemPointer(AIndex: TItemHandle): PItem;
		function GetItemsCount: Dword;
	public
		property Items[AIndex: TItemHandle]: TItem read GetItem; default;
		property ItemPointers[AIndex: TItemHandle]: PItem read GetItemPointer;
		property ItemsCount: Dword read GetItemsCount;
	public
		function FindHandle(const AKey: TKey): TItemHandle;
		function GetHandle(const AKey: TKey; out Created: Boolean): TItemHandle;
		function GetHandle(const AKey: TKey): TItemHandle;
		procedure FreeHandle(AHandle: TItemHandle);
	end;

	//TVariableChangedCallback = procedure ({Name: PChar; NewValue: Dword;} Parameter: Pointer); stdcall; // fastcall
	TVariableChangedCallback = procedure (
		Dummy: Pointer;
		NewValue: Dword;
		Name: PChar;
		Parameter: Pointer
	); register; // fastcall

	TManageHandleAction = (mhaReference, mhaUnreference);
	TManageHandleFunction = procedure ({hAgent: TJassObjectHandle; Action: TManageHandleAction;} Parameter: Pointer); stdcall; // fastcall
	//TManageHandleFunction = procedure (Dummy: Pointer; Action: TManageHandleAction; hAgent: TJassObjectHandle; Parameter: Pointer); register; // fastcall

	{ TInstance }

	PInstance = ^TInstance;
	TInstance = object
	public type
		TRegisters = array [0..255] of TScriptData;
		PRegisters = ^TRegisters;
		TVariables = specialize TSHashTable<PChar, TScriptData, TConstantStringHashKeyManager>;
		PVariables = ^TVariables;
		TStrToJassHandle = specialize TSHashTable<PChar, TJassHandle, TConstantStringHashKeyManager>;
		PStrToJassHandle = ^TStrToJassHandle;
		TCodePtrs = specialize TSGrowableArray<PInstruction>;
		PCodePtrs = ^TCodePtrs;
		TJassStringArrayItemManager = specialize TArrayOfObjectsManager<TJassString>;
		TInitFuncs = specialize TSLinkedList<TInitFuncAddr, TMissingInitialOffset>;
		PInitFuncs = ^TInitFuncs;
		TNameToFunc = specialize TSHashTable<PChar, TFuncAddr, TConstantStringHashKeyManager>;
		PNameToFunc = ^TNameToFunc;
		TCodePtrToName = specialize TSHashTable<PInstruction, TRCStringNode, THashlessKeyManager>;
		PCodePtrToName = ^TCodePtrToName;
		TStringTable = specialize TInstanceHandleTable<TJassString, TJassStringInstanceHandleTableItemManager, TJassStringArrayItemManager, PChar, TConstantStringHashKeyManager>;
		TCodeTable = specialize TInstanceHandleTable<PInstruction, specialize TDefaultInstanceHandleTableItemManager<PInstruction>, TDefaultArrayItemManager, PInstruction, THashlessKeyManager>;
	public
		field00: Dword;
		field04: Dword;
		field08: Dword;
		field0C: Dword;
		field10: Dword;
		field14: Dword;
		IsChild: LongBool;
		ChildsCount: Dword;
		CurrentOpcode: PInstruction;
		CodeStack: specialize TSGrowableArray<PInstruction>;
		Sleeping: LongBool;
		SleepParam: Pointer;
		Syncing: LongBool;
		SleepTimeout: Single;
		OperationsLimit: Dword;
		UntrustedCode: LongBool;
		RegistersCount: Dword;
		Registers: TRegisters;
		Handle: Dword;
		ParentHandle: Dword;
		Script: PJassScript;
		Globals: PVariables;
		Frames: specialize TSLinkedList<TFrame, TMissingInitialOffset>;
		unk_StrToJassHandleMap: PStrToJassHandle;
		Labels: PCodePtrs;
		StringTable: TStringTable;
		InitFuncs: PInitFuncs;
		NameToFuncAddr: PNameToFunc;
		CodeTable: TCodeTable;
		CodePtrToName: PCodePtrToName;
		VarChangedCallback: TVariableChangedCallback;
		VarChangedCallbackParam: Pointer;
		RefHandleCallback: TManageHandleFunction;
		RefHandleCallbackParam: Pointer;
	public
		procedure SetScriptDataValue(var AData: TScriptData; ANewValue: Dword; ANewType: TScriptDataType);
		procedure ChangeValueOfType(var ADestination: Dword; AType: TScriptDataType; AValue: Dword);
		procedure ClearJassArrayItems(JassArray: PJassArray; ItemType: TScriptDataType);
		procedure ClearScriptData(Data: PScriptData);
		procedure IncrementHandleReferences(hAgent: TJassObjectHandle);
		procedure DecrementHandleReferences(hAgent: TJassObjectHandle);
		procedure IncrementStringReferences(hString: TJassStringHandle);
		procedure DecrementStringReferences(hString: TJassStringHandle);
		function GetTopmostParent: PInstance;
	end;

	// environment

	TInstanceHandle = Dword;
	TScriptHandle = Dword;

	TScriptHandleNode = specialize TSHashNode<PJassScript, TScriptHandle>;

	TJassThreadLocal = object
		vtable: Pointer;
		RunningInstances: specialize TSGrowableArray<PInstance>;
		RunningInstancesCount: Int32;
		Natives: specialize TSHashTable<PChar, TNativeFunc, TStringHashKeyManager>;
		Scripts: specialize TSGrowableArray<PJassScript>;
		FreeScripts: specialize TSGrowableArray<TScriptHandle>;
		ScriptHandles: specialize TSHashTable<PJassScript, TScriptHandleNode, THashlessKeyManager>;
	  	Instances: specialize TSGrowableArray<PInstance>;
		FreeInstances: specialize TSGrowableArray<TInstanceHandle>;
		fieldA8, fieldAC: Dword;
	end;
	PJassThreadLocal = ^TJassThreadLocal;

const
	JASS_MAX_ARRAY_SIZE = 8192;
	DEFAULT_JASS_OPERATION_LIMIT = 300000;

var
	_RegisterNative: procedure ({Address: Pointer; Name: PChar;} Signature: PChar); stdcall; // fastcall
	_Compile: function ({Files: PScriptFile; Callback: TScriptCompileCallbackWar3;} ErrorCallbackParam: Dword; RiskLevel: Dword): TScriptHandle; stdcall; // fastcall
	_FreeScript: procedure ({ScriptId: TScriptHandle}); stdcall; // fastcall
	_CreateInstance: function ({Script: TScriptHandle}): TInstanceHandle;
	_RegisterInstance: function ({Instance: PInstance; DesiredSlot: TInstanceHandle}): TInstanceHandle; // fastcall
	_FreeInstance: procedure ({InstanceId: TInstanceHandle}); stdcall; // fastcall
	_RunInstance: function ({Instance: TInstanceHandle; FuncName: PChar;} out Result: Dword; CallInit, Resume: LongBool; OpLimit: Dword): TScriptExitCode; stdcall; // fastcall
	_CloneInstance: function ({hInstance: TInstanceHandle}): TInstanceHandle; stdcall; // fastcall
	_Instance_Run: function (Code: PInstruction; Result: PDword; OpLimit: Dword; Unused: Dword): TScriptExitCode; stdcall; // thiscall
	_Instance_CallCode: function ({this: PInstance,} pCode: PInstruction; Parameters: Pointer; out Result: Dword; OpLimit: Dword; Unused: Dword; DontResume: LongBool): TScriptExitCode; stdcall; // thiscall
	_Instance_ExecuteFunctionWithOptionalInit: function ({this: PInstance;} FunctionName: PChar; Result: PDword; InitGlobals: LongBool; OpLimit: Dword; Unused: Dword): TScriptExitCode; stdcall; // thiscall
	_ExecuteFunctionByHandle: function ({hInstance: TInstanceHandle; hFunction: Dword;} Parameters: Pointer; ScriptResult: PDword; OpLimit: Dword; Unused: Dword; ForceNewRun: LongBool): TScriptExitCode; stdcall; // fastcall
	_Instance_GetStringHandle: function ({Instance: PInstance;} Value: PChar): TJassStringHandle; stdcall; // thiscall

	JassArray_VMT: Pointer;

function GetJassThreadLocal: PJassThreadLocal;
function GetScriptDataTypeByLetter(Letter: Char; out DataType: TScriptDataType): Boolean;

implementation

function GetJassThreadLocal: PJassThreadLocal;
begin
	Result:= PJassThreadLocal(GetWc3Prop(piJassEnv));
end;

function GetScriptDataTypeByLetter(Letter: Char; out DataType: TScriptDataType): Boolean; inline;
begin
	Result:= True;

	case Letter of
		SCRIPT_TYPE_LETTER_VOID: DataType:= stVoid;
		SCRIPT_TYPE_LETTER_CODE: DataType:= stCode;
		SCRIPT_TYPE_LETTER_INTEGER: DataType:= stInteger;
		SCRIPT_TYPE_LETTER_REAL: DataType:= stReal;
		SCRIPT_TYPE_LETTER_STRING: DataType:= stString;
		SCRIPT_TYPE_LETTER_HANDLE: DataType:= stHandle;
		SCRIPT_TYPE_LETTER_BOOLEAN: DataType:= stBoolean;
		else Result:= False;
	end;
end;

procedure OnInit;
begin
	PtrUInt(_RegisterNative):= GameDll + $455110;
	PtrUInt(_Compile):= GameDll + $458900;
	PtrUInt(_FreeScript):= GameDll + $455800;
	PtrUInt(_CreateInstance):= GameDll + $455760;
	PtrUInt(_RegisterInstance):= GameDll + $44D960;
	PtrUInt(_FreeInstance):= GameDll + $453C50;
	PtrUInt(_RunInstance):= GameDll + $44B640;
	PtrUInt(_CloneInstance):= GameDll + $44D9B0;
	PtrUInt(_Instance_Run):= GameDll + $45E9D0;
	PtrUInt(_Instance_CallCode):= GameDll + $45FA30;
	PtrUInt(_Instance_ExecuteFunctionWithOptionalInit):= GameDll + $45F8B0;
	PtrUInt(_ExecuteFunctionByHandle):= GameDll + $44B6A0;
	PtrUInt(_Instance_GetStringHandle):= GameDLl + $45D210;
	JassArray_VMT:= Pointer(GameDll + $951060);
end;

{ TFrameStack }

procedure TFrameStack.Init;
var
	i: Integer;
begin
	Capacity:= System.Length(Items);
	for i:= 0 to High(Items) do begin
		Items[i]:= PScriptData( wc3memory.Allocate(SizeOf(TScriptData)) );
		Items[i]^.Init;
	end;
	Length:= 0;
end;

procedure TFrameStack.Done;
var
	i: Integer;
begin
	for i:= 0 to High(Items) do begin
		Items[i]^.Done;
		wc3memory.Free(Items[i]);
	end;
end;

function TFrameStack.GetEnumerator: TFrameStackEnumerator;
begin
	Result.Init(@Self);
end;

{ TFrameStackEnumerator }

function TFrameStackEnumerator.MoveNext: Boolean;
begin
	Inc(FPosition);
	Result:= FPosition < FOwner^.Length;
end;

function TFrameStackEnumerator.GetCurrent: PScriptData;
begin
	Result:= FOwner^.Items[FPosition];
end;

procedure TFrameStackEnumerator.Reset;
begin
	FPosition:= Dword(-1);
end;

constructor TFrameStackEnumerator.Init(AOwner: PFrameStack);
begin
	FOwner:= AOwner;
	Reset;
end;

{ TScriptData }

procedure TScriptData.Init;
begin
	HashKeyData.PageNode.Clear;
	HashKeyData.ItemsNode.Clear;
	InitializedType:= stVoid;
	_Type:= stVoid;
	Value:= 0;
	IsArgument:= False;
end;

procedure TScriptData.Done;
begin

end;

{ TFrame }

procedure TFrame.Init;
begin
	Node.Clear;
	Stack.Init;
	Locals.Init;
	IsFirstFrame:= False;
end;

procedure TFrame.Done;
begin
	Stack.Done;
	Locals.Done;
end;

{ TJassArray }

procedure TJassArray.Init;
begin
	vtable:= JassArray_VMT;
	List.Init;
end;

procedure TJassArray.Done;
begin
	List.Done;
end;

{ TDefaultInstanceHandleTableItemManager }

procedure TDefaultInstanceHandleTableItemManager.SetupItem(var AItem: T;
	const AKey: T);
begin
	AItem:= AKey;
end;

function TDefaultInstanceHandleTableItemManager.ExtractItemKey(var AItem: T): T;
begin
	Result:= AItem;
end;

procedure TDefaultInstanceHandleTableItemManager.ClearItem(var AItem: T);
begin
	// nothing to do
end;

{ TJassStringInstanceHandleTableItemManager }

procedure TJassStringInstanceHandleTableItemManager.SetupItem(
	var AItem: TJassString; const AKey: PChar);
begin
	AItem.SetContent(AKey);
end;

function TJassStringInstanceHandleTableItemManager.ExtractItemKey(
	var AItem: TJassString): PChar;
begin
	Result:= AItem.GetContent();
end;

procedure TJassStringInstanceHandleTableItemManager.ClearItem(
	var AItem: TJassString);
begin
	AItem.SetContent(nil);
end;

{ TInstance }

function TInstanceHandleTable.GetItem(AIndex: TItemHandle): TItem;
begin
	Result:= FItems^.Items[AIndex];
end;

function TInstanceHandleTable.GetItemPointer(AIndex: TItemHandle): PItem;
begin
	Result:= FItems^.ItemPointers[AIndex];
end;

function TInstanceHandleTable.GetItemsCount: Dword;
begin
	Result:= FItems^.Length;
end;

function TInstanceHandleTable.FindHandle(const AKey: TKey): TItemHandle;
var
	pNode: PItemHandleNode;
begin
	Result:= 0;

	if FHandleByKeyTable^.Find(AKey, pNode) then begin
		Result:= pNode^.Value;
	end;
end;

function TInstanceHandleTable.GetHandle(const AKey: TKey; out Created: Boolean
	): TItemHandle;
var
	pNode: PItemHandleNode;
	pNewItem: PItem;
begin
	Created:= False;

	if FHandleByKeyTable^.Find(AKey, pNode) then begin
		Result:= pNode^.Value;
		exit;
	end;

	if FFreeHandles^.Length > 0 then begin
		Result:= FFreeHandles^.Pop();
		pNewItem:= FItems^.ItemPointers[Result];
	end
	else begin
		pNewItem:= FItems^.GetNewItem();
		Result:= FItems^.Length - 1;
	end;

	TItemManager.SetupItem(pNewItem^, AKey);

	pNode:= FHandleByKeyTable^.CreateItem(AKey);
	pNode^.Value:= Result;

	Created:= True;
end;

function TInstanceHandleTable.GetHandle(const AKey: TKey): TItemHandle;
var
	Created: Boolean;
begin
	Result:= GetHandle(AKey, Created);
end;

procedure TInstanceHandleTable.FreeHandle(AHandle: TItemHandle);
var
	Item: PItem;
begin
	Item:= FItems^.ItemPointers[AHandle];
	FHandleByKeyTable^.Remove(TItemManager.ExtractItemKey(Item^));
	TItemManager.ClearItem(Item^);
	FFreeHandles^.Add(AHandle);
end;

procedure TInstance.SetScriptDataValue(var AData: TScriptData; ANewValue: Dword; ANewType: TScriptDataType);
begin
	with AData do begin
		if Value <> 0 then begin
			case _Type of
				stHandle: DecrementHandleReferences(Value);
				stString: DecrementStringReferences(Value);
			end;
		end;

		Value:= ANewValue;
		_Type:= ANewType;

		if ANewValue <> 0 then begin
			case ANewType of
				stHandle: IncrementHandleReferences(ANewValue);
				stString: IncrementStringReferences(ANewValue);
			end;
		end;
	end;
end;

procedure TInstance.ChangeValueOfType(var ADestination: Dword;
	AType: TScriptDataType; AValue: Dword);
begin
	case AType of
		stHandle: begin
			if ADestination <> 0 then DecrementHandleReferences(ADestination);
			ADestination:= AValue;
			if ADestination <> 0 then IncrementHandleReferences(ADestination);
		end;

		stString: begin
			if ADestination <> 0 then DecrementStringReferences(ADestination);
			ADestination:= AValue;
			if ADestination <> 0 then IncrementStringReferences(ADestination);
		end;

		else ADestination:= AValue;
	end;
end;

procedure TInstance.ClearJassArrayItems(JassArray: PJassArray; ItemType: TScriptDataType);
var
	i: Integer;
begin
	with JassArray^.List do begin
		for i:= 0 to Length - 1 do begin
			if FItems[i] <> 0 then begin
				case ItemType of
					stHandle: DecrementHandleReferences(FItems[i]);
					stString: DecrementStringReferences(FItems[i]);
				end;

				FItems[i]:= 0;
			end;
		end;
	end;
end;

procedure TInstance.ClearScriptData(Data: PScriptData);
begin
	with Data^ do begin
		case _Type of
			stHandle: DecrementHandleReferences(Value);
			stString: DecrementStringReferences(Value);

			stArrayOfHandle: if Value <> 0
				then ClearJassArrayItems(PJassArray(Value), stHandle);

			stArrayOfString: if Value <> 0
				then ClearJassArrayItems(PJassArray(Value), stString);
		end;

		_Type:= stVoid;
		Value:= 0;
	end;
end;

procedure TInstance.IncrementHandleReferences(hAgent: TJassObjectHandle);
begin
	asm
		mov hAgent, %ecx
		mov mhaReference, %edx
	end;
	RefHandleCallback(RefHandleCallbackParam);
end;

procedure TInstance.DecrementHandleReferences(hAgent: TJassObjectHandle);
begin
	asm
		mov hAgent, %ecx
		mov mhaUnreference, %edx
	end;
	RefHandleCallback(RefHandleCallbackParam);
end;

procedure TInstance.IncrementStringReferences(hString: TJassStringHandle);
begin
	if hString = 0 then exit;
	StringTable.FItems^.ItemPointers[hString]^.FReferences += 1;
end;

procedure TInstance.DecrementStringReferences(hString: TJassStringHandle);
begin
	if hString = 0 then exit;

	with StringTable.FItems^.ItemPointers[hString]^ do begin
		Dec(FReferences);

		if FReferences = 0 then begin
			StringTable.FreeHandle(hString);
		end;
	end;
end;

function TInstance.GetTopmostParent: PInstance;
var
	Environment: PJassThreadLocal;
begin
	Result:= @Self;
	Environment:= GetJassThreadLocal();

	while Result^.IsChild do begin
		Result:= Environment^.Instances[Result^.ParentHandle];
	end;
end;

{ TJassString }

procedure TJassString.SetContent(AContent: PChar);
begin
	FValue.Content:= AContent;
end;

function TJassString.GetContent: PChar;
begin
	Result:= FValue.Content;
end;

procedure TJassString.Init;
begin
	FValue.Init;
	FReferences:= 0;
end;

procedure TJassString.Done;
begin
	FValue.Done;
end;

{ THashedStringTable }

function THashedStringTable.GetItem(AIndex: Dword): PChar;
begin
	Result:= FItems[AIndex]^.HashKeyData.Key;
end;

function THashedStringTable.GetItemHash(AIndex: Dword): Dword;
begin
	Result:= FItems[AIndex]^.HashKeyData.Hash;
end;

function THashedStringTable.GetItemIndex(AItem: PChar; out AIndex: Dword
	): Boolean;
var
	HashedString: PHashedString;
begin
	Result:= FStrToItem.Find(AItem, HashedString);
	if Result
		then AIndex:= HashedString^.Index;
end;

function THashedStringTable.GetLength: Dword;
begin
	Result:= FItems.Length;
end;

begin
	wc3main.SubscribeOnInit(@OnInit);
end.

