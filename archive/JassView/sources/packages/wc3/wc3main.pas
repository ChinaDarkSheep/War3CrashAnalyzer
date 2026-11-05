unit wc3main;

{$Mode objfpc}{$H+}

interface

uses
	Windows,
	fgl;

type
	THandlerCallback = procedure;
	THandlerCallbacks = specialize TFPGList<THandlerCallback>;

var
	GameDll: HMODULE = 0;

procedure SubscribeOnInit(ACallback: THandlerCallback);
procedure SubscribeOnInitDone(ACallback: THandlerCallback);
procedure Init(AGameDll: HMODULE);

implementation

var
	InitHandlers, InitDoneHandlers: THandlerCallbacks;

procedure SubscribeOnInit(ACallback: THandlerCallback);
begin
	InitHandlers.Add(ACallback);
end;

procedure NotifyInitHandlers;
var
	Callback: THandlerCallback;
begin
	for Callback in InitHandlers do begin
		Callback();
	end;
end;

procedure SubscribeOnInitDone(ACallback: THandlerCallback);
begin
	InitDoneHandlers.Add(ACallback);
end;

procedure NotifyInitDoneHandlers;
var
	Callback: THandlerCallback;
begin
	for Callback in InitDoneHandlers do begin
		Callback();
	end;
end;

procedure Init(AGameDll: HMODULE);
begin
	GameDll:= AGameDll;
	NotifyInitHandlers();
	NotifyInitDoneHandlers();
end;

initialization
	InitHandlers:= THandlerCallbacks.Create();
	InitDoneHandlers:= THandlerCallbacks.Create();

finalization
	InitHandlers.Destroy;
	InitDoneHandlers.Destroy;

end.




















