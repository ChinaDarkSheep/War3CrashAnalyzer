unit pool;

interface

{$mode objfpc}{$H+}

uses
	fgl;

type

	{ TPool }

	generic TPool<TItem, TItemManager> = class
	private type
		TItems = specialize TFPGList<TItem>;
	private
		FParameter: Pointer;
		FAvailableItems: TItems;
	public
		function GetItem: TItem;
		procedure FreeItem(AItem: TItem);
	public
		constructor Create(AParameter: Pointer = nil);
		destructor Destroy; override;
	end;

	{ TDefaultPoolItemManager }

	generic TDefaultPoolItemManager<T> = object
	public
		class function CreateInstance({%H-}AParameter: Pointer): T; static;
		class procedure ClearInstance(AInstance: T; {%H-}AParameter: Pointer); static;
		class procedure DestroyInstance(AInstance: T; {%H-}AParameter: Pointer); static;
	end;

implementation

{ TDefaultPoolItemManager }

class function TDefaultPoolItemManager.CreateInstance(AParameter: Pointer): T;
begin
	Result:= T.Create;
end;

class procedure TDefaultPoolItemManager.ClearInstance(AInstance: T;
	AParameter: Pointer);
begin
	AInstance.Clear;
end;

class procedure TDefaultPoolItemManager.DestroyInstance(AInstance: T;
	AParameter: Pointer);
begin
	AInstance.Destroy;
end;

{ TPool }

function TPool.GetItem: TItem;
begin
	if FAvailableItems.Count > 0 then begin
		Result:= FAvailableItems.Last;
		FAvailableItems.Count:= FAvailableItems.Count - 1;
	end
	else begin
		Result:= TItemManager.CreateInstance(FParameter);
	end;
end;

procedure TPool.FreeItem(AItem: TItem);
begin
	TItemManager.ClearInstance(AItem, FParameter);
	FAvailableItems.Add(AItem);
end;

constructor TPool.Create(AParameter: Pointer);
begin
	FParameter:= AParameter;
	FAvailableItems:= TItems.Create;
end;

destructor TPool.Destroy;
var
	Item: TItem;
begin
	for Item in FAvailableItems do begin
		TItemManager.DestroyInstance(Item, FParameter);
	end;

	inherited Destroy;
end;

end.

