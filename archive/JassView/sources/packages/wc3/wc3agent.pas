unit wc3agent;

{$asmmode intel}
{$mode objfpc}{$H+}

interface

uses
	wc3main, wc3refcnt, wc3observer, wc3nettag;

type
	{ TAgent }

	TAgent = object (TObserver)
		kContainer: TNetTag;
		AgentObserver: TObserver;
	public
		function GetTypeId: Dword;
		function IsValid: Boolean;
		procedure Destroy;
	end;
	PAgent = ^TAgent;

	TAgentWar3 = object (TAgent)
		AgentWar3Flags: Dword;
	end;
	PAgentWar3 = ^TAgentWar3;

	TAgileData = object {...} end;
	PAgileData = ^TAgileData;

    TEnumAgentCallback = function (Instance: PAgent; Param: Pointer): Boolean;

    TPresenceRef_VMT = object (TRefCnt_VMT)
		Clear: procedure; stdcall;
	end;

	TPresenceRef = object (TRefCnt)
		NetTag: TNetTag;
	end;
	PPresenceRef = ^TPresenceRef;

	TAgentField_VMT = object (TPresenceRef_VMT)
		CopyTag_: procedure (Index: Integer; Container: Pointer); stdcall;
		GetParentContainer_: function: Pointer; stdcall;
		GetParentContainerValue_: function: PAgent; stdcall;
	end;

	TAgentField = TPresenceRef;
	PAgentField = PPresenceRef;

	TInteger = TAgentField;
	PInteger = ^TInteger;

	TFloat = TAgentField;
	PTFloat = ^TFloat;

procedure EnumTypeInstances(TypeId: Dword; Callback: TEnumAgentCallback; Param: Pointer = nil; EnumChilds: LongBool = false);

var
	ppAgileData: ^PAgileData;

implementation

var
	_CAgent_IsValid: function: LongBool; stdcall;
	_EnumTypeInstances: procedure ({TypeId: Dword; Callback: _TEnumAgileCallback;} Param: Pointer; EnumChilds: LongBool); stdcall; // fastcall

function TAgent.GetTypeId: Dword;
type
	TGetTypeId = function: Dword;
begin
	asm mov ecx, Self end;
	Result:= TGetTypeId(vtable + $1C)();
end;

function TAgent.IsValid: Boolean;
begin
	asm mov ecx,Self end;
	Result:= _CAgent_IsValid();
end;

procedure TAgent.Destroy;
var
	CAgent_virtual_Destroy: procedure;
begin
	Pointer(CAgent_virtual_Destroy):= PPointer(Self.vtable + $5C)^;
	asm mov ecx,Self end;
	CAgent_virtual_Destroy();
end;

type
	TEnumAgentParam = record
		Callback: TEnumAgentCallback;
		Param: Pointer;
	end;
	PEnumAgentParam = ^TEnumAgentParam;

function EnumTypeInstances_RawCallback(): LongBool; stdcall;
var
	Instance: PAgent;
	MyParam: PEnumAgentParam;
begin
	asm
		mov Instance,ecx
		mov MyParam,edx
	end;

	with MyParam^ do begin
		Result:= Callback(Instance, Param);
	end;
end;

procedure EnumTypeInstances(TypeId: Dword; Callback: TEnumAgentCallback; Param: Pointer; EnumChilds: LongBool);
var
	MyParam: TEnumAgentParam;
begin
	MyParam.Callback:= Callback;
	MyParam.Param:= Param;

	asm
		mov ecx,TypeId
		lea edx,EnumTypeInstances_RawCallback
	end;
	_EnumTypeInstances(@MyParam, EnumChilds);
end;

procedure init;
begin
	Pointer(_CAgent_IsValid):= Pointer(GameDll + $0418A0);
	Pointer(_EnumTypeInstances):= Pointer(GameDll + $46D1B0);
	Pointer(ppAgileData):= Pointer(GameDLl + $AB7368);
end;

initialization
	wc3main.SubscribeOnInit(@init);

end.

