unit wc3_observer_callback;

{$mode objfpc}{$H+}
{$ASMMODE INTEL}

interface

uses
	wc3observer;

type
	TEventCallback = function (var Event: TEvent): Boolean;

	{ TCallbackWrapperObserver }

	TCallbackWrapperObserver = object (TObserver)
	public
		Callback: TEventCallback;
	public
		procedure Init(ACallback: TEventCallback);
	end;
	PCallbackWrapperObserver = ^TCallbackWrapperObserver;

implementation

procedure CallbackWrapperObserver_Release; stdcall; forward;
procedure CallbackWrapperObserver_Delete(FreeMem: Boolean); stdcall; forward;
procedure CallbackWrapperObserver_Subscribe({%H-}EventId, {%H-}PassedEventId: Dword; constref {%H-}Listener: TObserver); stdcall; forward;
function CallbackWrapperObserver_Notify(var Event: TEvent): LongBool; stdcall; forward;
function CallbackWrapperObserver_PostEvent(var {%H-}Event: TEvent): LongBool; stdcall; forward;
function CallbackWrapperObserver_PostEventAs({%H-}EventId: Dword; var {%H-}Event: TEvent): LongBool; stdcall; forward;

const
	CallbackWrapperObserver_VMT: TObserver_VMT =
	(
		Release:   @CallbackWrapperObserver_Release;
		Delete:    @CallbackWrapperObserver_Delete;
		Subscribe: @CallbackWrapperObserver_Subscribe;
		Notify:    @CallbackWrapperObserver_Notify;
		PostEvent: @CallbackWrapperObserver_PostEvent;
		PostEventAs: @CallbackWrapperObserver_PostEventAs;
	);

procedure CallbackWrapperObserver_Release; stdcall;
begin
	CallbackWrapperObserver_Delete(true);
end;

procedure CallbackWrapperObserver_Delete(FreeMem: Boolean); stdcall;
var
	this: PCallbackWrapperObserver;
begin
	asm mov this, ecx end;

	if FreeMem then begin
		Dispose(this);
	end;
end;

procedure CallbackWrapperObserver_Subscribe(EventId, PassedEventId: Dword; constref Listener: TObserver); stdcall;
begin

end;

function CallbackWrapperObserver_Notify(var Event: TEvent): LongBool; stdcall;
var
	this: PCallbackWrapperObserver;
begin
	asm mov this, ecx end;
	Result:= this^.Callback(Event);
end;

function CallbackWrapperObserver_PostEvent(var Event: TEvent): LongBool; stdcall;
begin
	Result:= false;
end;

function CallbackWrapperObserver_PostEventAs(EventId: Dword; var Event: TEvent): LongBool; stdcall;
begin
	Result:= false;
end;

{ TCallbackWrapperObserver }

procedure TCallbackWrapperObserver.Init(ACallback: TEventCallback);
begin
	vtable:= @CallbackWrapperObserver_VMT;
	References:= 0;
	Registry:= nil;
	Callback:= ACallback;
end;

end.

