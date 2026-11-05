unit handletables;

{$mode objfpc}{$H+}
{$ModeSwitch advancedrecords}

interface

uses
	SysUtils, Math, fgl, Comparators;

type

	{ THandleTableM }

	generic THandleTableM<T, TComparator> = class
	private type

		{ TSlot }

		TSlot = record
			Occupied: Boolean;
			Value: T;
			class operator = (const a,b: TSlot): Boolean;
		end;
		PSlot = ^TSlot;

		TSlots = specialize TFPGList<TSlot>;
		THandles = specialize TFPGList<Integer>;
		TComparableItem = specialize TComparable<T, TComparator>;
		TObjectToHandleMap = specialize TFPGMap<TComparableItem, Integer>;
	private
		FSlots: TSlots;
		FFreeHandles: THandles;
		FValueToHandle: TObjectToHandleMap;
	private
		function AllocateHandle(AValue: T): Integer;
		function GetKey(AIndex: Integer): Integer;
		function GetData(AIndex: Integer): T;
		function GetCount: Integer;
		function GetSlot(AIndex: Integer): PSlot;
	private
		property Slots[AIndex: Integer]: PSlot read GetSlot;
	protected
		function IsValidHandle(AHandle: Integer): Boolean;
	public
		function GetHandle(const AValue: T): Integer;
		procedure InsertValue(AHandle: Integer; const AValue: T);
		function GetValue(AHandle: Integer; out Value: T): Boolean;
		function GetValue(AHandle: Integer): T;
		function CreateHandle(const AValue: T): Integer;
		procedure FreeHandle(AHandle: Integer);
		procedure Clear;
	public
		property Items[AHandle: Integer]: T read GetValue write InsertValue; default;
		property Keys[AIndex: Integer]: Integer read GetKey;
		property Data[AIndex: Integer]: T read GetData;
		property Count: Integer read GetCount;
	public
		constructor Create;
		destructor Destroy; override;
	end;

	generic THandleTable<T> = class(specialize THandleTableM<T, specialize TValueComparator<T>>);

implementation

{ THandleTableM.TSlot }

class operator THandleTableM.TSlot.=(const a, b: TSlot): Boolean;
begin
	Result:= a.Value = b.Value;
end;

{ THandleTableM }

function THandleTableM.AllocateHandle(AValue: T): Integer;
var
	Slot: TSlot;
begin
	Slot.Occupied:= True;
	Slot.Value:= AValue;

	if FFreeHandles.Count > 0 then begin
		Result:= FFreeHandles.Last;
		FFreeHandles.Count:= FFreeHandles.Count - 1;
		Slots[Result-1]^:= Slot;
	end else begin
		Result:= FSlots.Add(Slot) + 1;
	end;

	FValueToHandle[AValue]:= Result;
end;

function THandleTableM.GetKey(AIndex: Integer): Integer;
begin
	Result:= FValueToHandle.Data[AIndex];
end;

function THandleTableM.GetData(AIndex: Integer): T;
begin
	Result:= FValueToHandle.Keys[AIndex];
end;

function THandleTableM.GetCount: Integer;
begin
	Result:= FValueToHandle.Count;
end;

function THandleTableM.GetSlot(AIndex: Integer): PSlot;
begin
	Result:= @FSlots.List^[AIndex];
end;

function THandleTableM.IsValidHandle(AHandle: Integer): Boolean;
begin
	Result:= InRange(AHandle, 1, FSlots.Count);
end;

function THandleTableM.GetHandle(const AValue: T): Integer;
var
	Index: Integer;
begin
	Index:= FValueToHandle.IndexOf(AValue);

	if Index <> -1 then begin
		Result:= FValueToHandle.Data[Index];
	end else begin
		Result:= AllocateHandle(AValue);
	end;
end;

procedure THandleTableM.InsertValue(AHandle: Integer; const AValue: T);
var
	Index, OldSlotsCount, i: Integer;
	NewlyAllocated: Boolean = False;
	Slot: PSlot;
begin
	Index:= AHandle - 1;

	if Index >= FSlots.Count then begin
		OldSlotsCount:= FSlots.Count;
		FSlots.Count:= Index + 1;

		for i:= OldSlotsCount to FSlots.Count - 1 - 1 do begin
			FFreeHandles.Add(i);
		end;

		NewlyAllocated:= True;
	end;

	Slot:= Slots[Index];

	if not NewlyAllocated then begin
		if Slot^.Occupied then
			FValueToHandle.Remove(Slot^.Value)
		else
			FFreeHandles.Remove(AHandle);
	end;

	Slot^.Occupied:= True;
	Slot^.Value:= AValue;

	FValueToHandle[AValue]:= AHandle;
end;

function THandleTableM.GetValue(AHandle: Integer; out Value: T): Boolean;
var
	Slot: PSlot;
begin
	Result:= False;

	if IsValidHandle(AHandle) then begin
		Slot:= Slots[AHandle-1];

		if Slot^.Occupied then begin
			Value:= Slot^.Value;
			Result:= True;
		end;
	end;
end;

function THandleTableM.GetValue(AHandle: Integer): T;
begin
	if not GetValue(AHandle, Result) then
		raise Exception.CreateFmt('Invalid handle: %d', [AHandle]);
end;

function THandleTableM.CreateHandle(const AValue: T): Integer;
var
	Index: Integer;
begin
	Index:= FValueToHandle.IndexOf(AValue);

	if Index <> -1 then begin
		raise Exception.Create('Handle for object already exists!');
	end else begin
		Result:= AllocateHandle(AValue);
	end;
end;

procedure THandleTableM.FreeHandle(AHandle: Integer);
//var
//	Slot: PSlot;
begin
	//if IsValidHandle(AHandle) then begin
	//	Slot:= Slots[AHandle-1];
 //
	//	if Slot^.Occupied then begin
	//		Slot^.Occupied:= False;
 //
	//		FFreeHandles.Add(AHandle);
	//		FValueToHandle.Remove(Slot^.Value);
	//	end;
	//end;
end;

procedure THandleTableM.Clear;
begin
	FSlots.Clear;
	FFreeHandles.Clear;
	FValueToHandle.Clear;;
end;

constructor THandleTableM.Create;
begin
	FSlots:= TSlots.Create;
	FFreeHandles:= THandles.Create;
	FValueToHandle:= TObjectToHandleMap.Create;
	FValueToHandle.Sorted:= True;
end;

destructor THandleTableM.Destroy;
begin
	FSlots.Free;
	FFreeHandles.Free;
	FValueToHandle.Free;

	inherited Destroy;
end;

end.

