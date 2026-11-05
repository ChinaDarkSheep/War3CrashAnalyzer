unit wc3observer;

{$mode objfpc}{$H+}
{$ASMMODE INTEL}

interface

uses
	wc3main, wc3refcnt;

type
	TEvent = object (TRefCnt)
		Id: Dword;
		Parameter: Dword;
	end;
	PEvent = ^TEvent;

	{ TObserver }

	PObserver = ^TObserver;

	TObserver = object (TRefCnt)
		Registry: Pointer;
	public
		procedure Subscribe(EventId: Dword; PassedEventId: Dword; Listener: PObserver);
		procedure Subscribe(EventId: Dword; Listener: PObserver);
		procedure Unsubscribe(EventId: Dword; Listener: PObserver);
		function Notify(var Event: TEvent): Boolean;
		function Emit(var Event: TEvent): Boolean;
	end;

	TObserver_VMT = object (TRefCnt_VMT)
		Subscribe: procedure (EventId: Dword; PassedEventId: Dword; constref Lisneter: TObserver); stdcall;
		Notify: function (var Event: TEvent): LongBool; stdcall;
		PostEvent: function (var Event: TEvent): LongBool; stdcall;
		PostEventAs: function (EventId: Dword; var Event: TEvent): LongBool; stdcall;
	end;
	PObserver_VMT = ^TObserver_VMT;

var
	_CObserver_Unsubscribe: procedure (EventId: Dword; Listener: PObserver); stdcall;

implementation

{ TObserver }

procedure TObserver.Subscribe(EventId: Dword; PassedEventId: Dword;
	Listener: PObserver);
begin
	asm mov ecx, Self end;
	PObserver_VMT(vtable)^.Subscribe(EventId, PassedEventId, Listener^);
end;

procedure TObserver.Subscribe(EventId: Dword; Listener: PObserver);
begin
	Subscribe(EventId, EventId, Listener);
end;

procedure TObserver.Unsubscribe(EventId: Dword; Listener: PObserver);
begin
	asm mov ecx, Self end;
	_CObserver_Unsubscribe(EventId, Listener);
end;

function TObserver.Notify(var Event: TEvent): Boolean;
begin
	asm mov ecx, Self end;
	Result:= PObserver_VMT(Self.vtable)^.Notify(Event);
end;

function TObserver.Emit(var Event: TEvent): Boolean;
begin
	asm mov ecx, Self end;
	Result:= PObserver_VMT(Self.vtable)^.PostEvent(Event);
end;

procedure OnInit;
begin
	Pointer(_CObserver_Unsubscribe):= Pointer(GameDll + $62A570);
end;

begin
	wc3main.SubscribeOnInit(@OnInit);
end.

