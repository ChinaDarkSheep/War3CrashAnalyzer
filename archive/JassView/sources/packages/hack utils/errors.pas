unit errors;

{$mode objfpc}{$H+}

interface

uses
	Windows, Classes, SysUtils, SysConst;

procedure CallWithErrorHandling(f: TProcedure);
procedure ShowError(Message: String);
procedure RaiseLastOSError(Message: String);
procedure RaiseLastOSError(Message: String; Arguments: array of const);
procedure RaiseLastOSError(Message: String; LastError: Dword);
procedure RaiseLastOSError(Message: String; Arguments: array of const; LastError: Dword);

implementation

procedure CallWithErrorHandling(f: TProcedure);
begin
	try
		f();
	except
		on e: Exception do begin
			ShowError(e.Message);
			raise e;
		end;
	end;
end;

procedure ShowError(Message: String);
begin
	MessageBoxW(0, PWideChar(Unicodestring(Message)), nil, MB_ICONERROR);
end;

procedure RaiseLastOSError(Message: String);
begin
	RaiseLastOSError(Message, GetLastError());
end;

procedure RaiseLastOSError(Message: String; Arguments: array of const);
begin
    RaiseLastOSError(Format(Message, Arguments));
end;

procedure RaiseLastOSError(Message: String; LastError: Dword);
var
	e: EOSError;
begin
	if LastError <> ERROR_SUCCESS then
		e:= EOSError.CreateFmt(
			Message + #13#10 + SOSError,
			[
				LastError,
				SysErrorMessage(LastError)
			]
		)
	else
		e:= EOSError.Create(SUnkOSError);

	e.ErrorCode:= LastError;

	raise e;
end;

procedure RaiseLastOSError(Message: String; Arguments: array of const;
	LastError: Dword);
begin
	RaiseLastOSError(Format(Message, Arguments), LastError);
end;

end.

