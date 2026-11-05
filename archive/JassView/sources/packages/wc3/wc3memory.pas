unit wc3memory;

{$mode objfpc}{$H+}

interface

const
	STORM_NAME = 'storm.dll';

function SMemAlloc(Size: PtrUInt; SourceFile: PChar; SourceLine: Integer; Flags: Dword): Pointer; stdcall; external STORM_NAME index 401;
function SMemFree(Memory: Pointer; SourceFile: PChar; SourceLine: Integer; Flags: Dword): Pointer; stdcall; external STORM_NAME index 403;
function SMemReAlloc(Memory: Pointer; NewSize: PtrUInt; SourceFile: PChar; SourceLine: Integer; Flags: Dword): Pointer; stdcall; external STORM_NAME index 405;

function Allocate(Size: PtrUInt): Pointer;
function ReAllocate(Memory: Pointer; NewSize: PtrUInt): Pointer;
procedure Free(Memory: Pointer);
function CloneString(s: PChar): PChar;

implementation

function Allocate(Size: PtrUInt): Pointer;
begin
	Result:= SMemAlloc(Size, nil, 0, 0);
end;

function ReAllocate(Memory: Pointer; NewSize: PtrUInt): Pointer;
begin
	Result:= SMemReAlloc(Memory, NewSize, nil, 0, 0);
end;

procedure Free(Memory: Pointer);
begin
	SMemFree(Memory, nil, 0, 0);
end;

function CloneString(s: PChar): PChar;
var
	Length: Integer;
begin
	Length:= StrLen(s);
	Result:= Allocate(Length + 1);
	Move(s^, Result^, Length);
	Result[Length]:= #0;
end;

end.

