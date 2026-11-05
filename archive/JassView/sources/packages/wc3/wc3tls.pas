unit wc3tls;

{$mode objfpc}{$H+}

interface

uses
	Windows,
	wc3main;

var
	g_Wc3Props: PPointer;
	g_Wc3PropsTlsIndex: PDword;

procedure CopyTLS;

implementation

procedure CopyTLS;
begin
	if g_Wc3Props^ <> nil then begin
		TlsSetValue(g_Wc3PropsTlsIndex^, g_Wc3Props^);
	end;
end;

procedure Init;
begin
	Pointer(g_Wc3Props):= Pointer(GameDll + $ADA848);
	Pointer(g_Wc3PropsTlsIndex):= Pointer(GameDll + $AB7BF4);
end;

initialization
	wc3main.SubscribeOnInit(@Init);

end.

