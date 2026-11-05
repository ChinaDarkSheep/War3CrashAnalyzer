unit wc3Debug;

{$mode objfpc}{$H+}
{$ASMMODE INTEL}

interface

uses
  Windows, SysUtils;

procedure DebugOut(msg: String);
procedure DebugOut(fmt: String; args: array of const);

implementation

procedure DebugOut(msg: String);
var
	DataStruct: TCopyDataStruct;
begin
	with DataStruct do begin
		dwData:= 0;
		cbData:= Length(msg);
		lpData:= @msg[1];
	end;

	SendMessage(FindWindow(nil,'War3Log'), WM_COPYDATA, 0, LPARAM(@DataStruct));
end;

procedure DebugOut(fmt: String; args: array of const);
begin
	DebugOut(Format(fmt, args));
end;

end.

