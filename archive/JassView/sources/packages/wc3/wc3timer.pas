unit wc3timer;

{$mode objfpc}{$H+}
{$ASMMODE INTEL}

interface

uses
	wc3main;

type
	TTimerCallback = procedure (Param: Pointer);

function StartTimer(Callback: TTimerCallback; Timeout: Single; Param: Pointer; Periodic: Boolean): Pointer;
procedure DestroyTimer(Timer: Pointer);

var
	_AddTimerEventHandler: function ({Callback: Pointer; Param: PtrInt;} Timeout: Single): Dword; stdcall; // fastcall
	_RemoveTimerEventHandler: procedure ({id: Dword}); // fastcall

implementation

function AddTimerEventHandler(Callback: Pointer; Param: Pointer; Timeout: Single): Dword;
begin
	asm
		mov ecx,Callback
		mov edx,Param
	end;
	Result:= _AddTimerEventHandler(Timeout);
end;

procedure RemoveTimerEventHandler(id: Dword);
begin
	asm mov ecx,id end;
	_RemoveTimerEventHandler();
end;

type
	TTimer = record
		Callback: TTimerCallback;
		Param: Pointer;
		Periodic: Boolean;
		Id: Dword;
	end;
	PTimer = ^TTimer;

function TimerCallback: LongBool; stdcall;
var
	Timeout: PSingle;
	Timer: PTimer;
begin
	asm
		mov Timeout,ecx
		mov Timer,edx
	end;

	with Timer^ do begin
		Callback(Param);
	end;

	if Timer^.Periodic then begin
		Timer^.Id:= AddTimerEventHandler(@wc3timer.TimerCallback, Timer, Timeout^);
	end
	else begin
		Dispose(Timer);
	end;

	Result:= True;
end;

function StartTimer(Callback: TTimerCallback; Timeout: Single; Param: Pointer; Periodic: Boolean): Pointer;
var
	Timer: PTimer;
begin
	New(Timer);

	Timer^.Callback:= Callback;
	Timer^.Param:= Param;
	Timer^.Periodic:= Periodic;
	Timer^.Id:= AddTimerEventHandler(@TimerCallback, Timer, Timeout);

	Result:= Timer;
end;

procedure DestroyTimer(Timer: Pointer);
var
	t: PTimer absolute Timer;
begin
	if t^.Id <> 0 then begin
		RemoveTimerEventHandler(t^.Id);
	end;
	Dispose(t);
end;

procedure Init;
begin
	Pointer(_AddTimerEventHandler):= Pointer(GameDll + $62B510);
	Pointer(_RemoveTimerEventHandler):= Pointer(GameDll + $62B710);
end;

initialization
	wc3main.SubscribeOnInit(@Init);

end.




















