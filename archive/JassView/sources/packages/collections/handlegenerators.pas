unit handlegenerators;

{$mode objfpc}{$H+}

interface

uses
	fgl;

type

	{ THandleGenerator }

	THandleGenerator = class
	public type
		THandle = Dword;
	private type
		THandleList = specialize TFPGList<THandle>;
	private
		FCount: Dword;
		FFreeHandles: THandleList;
	public
		function Get: THandle;
		procedure Free(AHandle: THandle);
	public
		constructor Create;
		destructor Destroy; override;
	end;

implementation

{ THandleGenerator }

function THandleGenerator.Get: THandle;
begin
	if FFreeHandles.Count > 0 then begin
		Result:= FFreeHandles.Last;
		FFreeHandles.Count:= FFreeHandles.Count - 1;
	end
	else begin
		Result:= FCount;
		Inc(FCount);
	end;
end;

procedure THandleGenerator.Free(AHandle: THandle);
var
	Correct, Occupied: Boolean;
begin
	Correct:= (AHandle < FCount);
	Occupied:= FFreeHandles.IndexOf(AHandle) <> -1;

	if Correct and Occupied then begin
		FFreeHandles.Add(AHandle);
	end;
end;

constructor THandleGenerator.Create;
begin
	FCount:= 0;
	FFreeHandles:= THandleList.Create;
end;

destructor THandleGenerator.Destroy;
begin
	FFreeHandles.Destroy;
	inherited Destroy;
end;

end.

