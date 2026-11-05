unit wc3typeid;

{$mode objfpc}{$H+}

interface

uses
	SysUtils;

function StrToTypeId(s: String): Dword;

implementation

function StrToTypeId(s: String): Dword;
begin
	if Length(s) <> 4 then
		raise Exception.CreateFmt('String "%s" can''t be converted to type id.', [s]);

	Result:= SwapEndian(PDword(@s[1])^);
end;

end.

