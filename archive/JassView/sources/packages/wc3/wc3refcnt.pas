unit wc3refcnt;

{$mode objfpc}{$H+}
{$modeswitch advancedrecords}
{$AsmMode INTEL}

interface

uses
	wc3main;

type
	TRefCnt_VMT = object
		Release: procedure; stdcall;
		Delete: procedure (FreeMem: Boolean); stdcall;
	end;
	PRefCnt_VMT = ^TRefCnt_VMT;

	{ TRefCnt }

	TRefCnt = object
		vtable: Pointer;
		References: Dword;
	public
		procedure Release;
		procedure IncRef;
		procedure DecRef;
	end;
	PRefCnt = ^TRefCnt;

var
	p_TRefCnt_VMT: PRefCnt_VMT;

implementation

{ TRefCnt }

procedure TRefCnt.Release;
begin
	asm mov ecx,Self end;
	PRefCnt_VMT(vtable)^.Release();
end;

procedure TRefCnt.IncRef;
begin
	Inc(References);
end;

procedure TRefCnt.DecRef;
begin
	Dec(References);

	if References = 0 then begin
		Release;
	end;
end;

procedure Init;
begin
	p_TRefCnt_VMT:= Pointer(GameDll+$8765F8);
end;

initialization
	wc3main.SubscribeOnInit(@Init);

end.

