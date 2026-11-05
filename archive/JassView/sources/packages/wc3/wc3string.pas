unit wc3string;

{$mode objfpc}{$H+}

interface

uses
	wc3main, wc3memory, wc3refcnt, wc3collections;

type
	TStringRep_VMT = object (TRefCnt_VMT)
		Dereference: procedure;
	end;
	PStringRep_VMT = ^TStringRep_VMT;

	TStringRep = object (TRefCnt)
		HashKeyData: specialize THashKeyData<PChar>;
	end;
	PStringRep = ^TStringRep;

	{ TRCString }

	TRCString = object (TRefCnt)
	private
		FRepresentation: PStringRep;
	private
		procedure SetRepresentation(ARepresentation: PStringRep);
		procedure SetContent(AString: PChar);
		function GetContent: PChar;
	public
		property Representation: PStringRep read FRepresentation write SetRepresentation;
		property Content: PChar read GetContent write SetContent;
	public
		procedure Clear;
		{constructor} procedure Init;
		{destructor} procedure Done;
	end;
	PRCString = ^TRCString;

	{ TStringManager }

	TStringManager = object
	public
		FStorage: specialize TSHashTable<PChar, TStringRep, TStringHashKeyManager>;
	public
		function GetRepresentationFor(AString: PChar): PStringRep;
		{constructor} procedure Init;
		{destructor} procedure Done;
	end;
	PStringManager = ^TStringManager;

var
	p_TStringManager_VMT: Pointer;
	p_TRCString_VMT: PRCString;
	ppStringManager: ^PStringManager;
	pNullRep: PStringRep;

implementation

function GetStringManager: PStringManager;
begin
	if ppStringManager^ <> nil then
		Result:= ppStringManager^
	else begin
		Result:= wc3memory.Allocate(SizeOf(TStringManager));
		Result^.Init;
		ppStringManager^:= Result;
	end;
end;

{ TStringManager }

function TStringManager.GetRepresentationFor(AString: PChar): PStringRep;
begin
	if AString = nil then begin
		Result:= pNullRep;
	end
	else if not FStorage.Find(AString, Result) then begin
		Result:= FStorage.CreateItem(AString);
	end;
end;

procedure TStringManager.Init;
begin
	FStorage.Init;
	FStorage.vtable:= p_TStringManager_VMT;
end;

procedure TStringManager.Done;
begin
	FStorage.Done;
end;

{ TRCString }

procedure TRCString.SetRepresentation(ARepresentation: PStringRep);
begin
	if FRepresentation <> nil then
		FRepresentation^.DecRef;

	FRepresentation:= ARepresentation;

	if FRepresentation <> nil then
		FRepresentation^.IncRef;
end;

procedure TRCString.SetContent(AString: PChar);
begin
	Representation:= ppStringManager^^.GetRepresentationFor(AString);
end;

function TRCString.GetContent: PChar;
begin
	if Representation <> nil then
		Result:= Representation^.HashKeyData.Key
	else
		Result:= nil;
end;

procedure TRCString.Clear;
begin
	Representation:= nil;
end;

procedure TRCString.Init;
begin
	inherited;
	vtable:= p_TRCString_VMT;
	FRepresentation:= nil;
end;

procedure TRCString.Done;
begin
	vtable:= p_TRCString_VMT;
	Representation:= nil;
	inherited;
end;

procedure Init;
begin
	p_TStringManager_VMT:= Pointer(GameDll+$9546D4);
	p_TRCString_VMT:= Pointer(GameDll+$87688C);
	ppStringManager:= Pointer(GameDll+$AB7D14);
	pNullRep:= Pointer(GameDll+$A85E18);

	pNullRep^.IncRef;
end;

initialization
	wc3main.SubscribeOnInit(@Init);

end.

