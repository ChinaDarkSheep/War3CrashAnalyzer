unit wc3collections;

{$mode objfpc}{$H+}
{$AsmMode INTEL}


interface

uses
	SysUtils,
	wc3memory, wc3stringhash;

type
	// lazarus kostil : ne rabotaet

	// generic DeclarePointer<T> = object
	// 	type P = ^T;
	// end;

	// array

	{ TArrayItemManager }

	//generic TArrayItemManager<TItem> = object
	//public
	//	procedure Initialize(out AItem: TItem); abstract;
	//	procedure Finalize(out AItem: TItem); abstract;
	//	procedure Copy(const ASource: TItem; out ADestination: TItem); abstract;
	//end;

	{ TDefaultArrayItemManager }

	TDefaultArrayItemManager = object
	public
		procedure Initialize(out {%H-}AItem; {%H-}Size: SizeUInt); static; inline;
		procedure Finalize(out {%H-}AItem; {%H-}Size: SizeUInt); static; inline;
		procedure Copy(out ADestination; const ASource; Size: SizeUInt); static; inline;
	end;

	{ TArrayOfObjectsManager }

	generic TArrayOfObjectsManager<TItem> = object
	public
		procedure Initialize(out AItem: TItem; {%H-}Size: SizeUInt); static; inline;
		procedure Finalize(out AItem: TItem; {%H-}Size: SizeUInt); static; inline;
		procedure Copy(out ADestination: TItem; const ASource: TItem; {%H-}Size: SizeUInt); static; inline;
	end;

	{ TMissingArrayItemManager }

	TMissingArrayItemManager = object
	public
		procedure Initialize(out {%H-}AItem; {%H-}Size: SizeUInt); static; inline;
		procedure Finalize(out {%H-}AItem; {%H-}Size: SizeUInt); static; inline;
		procedure Copy(out {%H-}ADestination; const {%H-}ASource; {%H-}Size: SizeUInt); static; inline;
	end;

	{ TSArrayM }

	generic TSArrayM<T, TItemManager> = object
	public type
		P = ^T;
		PSArray = ^TSArrayM;

		{ TArrayEnumerator }

		TArrayEnumerator = class
		private
			FArray: PSArray;
			FCurrent: Dword;
		public
			constructor Create(AArray: PSArray);
			function GetCurrent: T;
			function MoveNext: Boolean;
			procedure Reset;
			property Current: T read GetCurrent;
		end;

		{ TArrayItemPointers }

		TArrayItemPointers = object
		public type

			PArrayItemPointers = ^TArrayItemPointers;

			{ TArrayItemPointersEnumerator }

			TArrayItemPointersEnumerator = object
			private
				FOwner: PSArray;
				FCurrentIndex: Dword;
			public
				{constructor}procedure Init(AOwner: PSArray);
				function GetCurrent: P;
				function MoveNext: Boolean;
				procedure Reset;
				property Current: P read GetCurrent;
			end;
		private
			FOwner: PSArray;
			function GetItem(AIndex: Dword): P;
		public
			property Items[AIndex: Dword]: P read GetItem; default;
		public
			constructor Init(AOwner: PSArray);
			function GetEnumerator: TArrayItemPointersEnumerator;
		end;
	private
		procedure SetLength(ALength: Dword);
		procedure SetCapacity(ACapacity: Dword);
		function GetItem(AIndex: Dword): T;
		procedure SetItem(AIndex: Dword; const AValue: T);
		function GetItemPointers: TArrayItemPointers;
	public
		FCapacity: Dword;
		FLength: Dword;
		FItems: P;
	public
		property Length: Dword read FLength write SetLength;
		property Capacity: Dword read FCapacity write SetCapacity;
		property Items[AIndex: Dword]: T read GetItem write SetItem; default;
		property ItemPointers: TArrayItemPointers read GetItemPointers;
	public
		{constructor}procedure Init;
		{destructor}procedure Done;
		function Add(AValue: T): Dword;
		function GetNewItem: P;
		function Pop: T;
		function GetEnumerator: TArrayEnumerator;
	end;

	generic TSArray<T> = object (specialize TSArrayM<T, TDefaultArrayItemManager>) end;

	{ TSGrowableArrayM }

	generic TSGrowableArrayM<T, TItemManager> = object (specialize TSArrayM<T, TItemManager>)
	public
		FGrowFactor: Dword;
	public
		{constructor}procedure Init;
	end;

	generic TSGrowableArray<T> = object (specialize TSGrowableArrayM<T, TDefaultArrayItemManager>) end;

	// linked list

	{ TSLinkedNode }

	generic TSLinkedNode<P> = object
	public type
		PNode = ^TSLinkedNode;
	public
		Previous: PNode;
		Value: P;
	private
		function IsLinked: Boolean;
	public
		property Linked: Boolean read IsLinked;
	public
		procedure Clear;
		procedure Lock;
	end;

	{ TMissingInitialOffset }

	TMissingInitialOffset = object
	public
		class function GetValue: SizeUInt; static;
	end;

	{ TSLinkedList }

	generic TSLinkedList<T, TInitialOffset> = object
	public type
		P = ^T;
		PSLinkedList = ^TSLinkedList;
		TNode = specialize TSLinkedNode<P>;
		PNode = ^TNode;

		{ TLinkedListEnumerator }

		TLinkedListEnumerator = class
		private
			FList: PSLinkedList;
			FCurrent: P;
			FCurrentNode: PNode;
		public
			constructor Create(AList: PSLinkedList);
			function GetEnumerator: TLinkedListEnumerator;
			function GetCurrent: P;
			function MoveNext: Boolean;
			procedure Reset;
			property Current: P read GetCurrent;
		end;

		{ TLinkedListReversedEnumerator }

		TLinkedListReversedEnumerator = class
		private
			FList: PSLinkedList;
			FCurrent: P;
			FCurrentNode: PNode;
		public
			constructor Create(AList: PSLinkedList);
			function GetCurrent: P;
			function MoveNext: Boolean;
			procedure Reset;
			property Current: P read GetCurrent;
		end;

	public
		FOffset: Dword;
		FRoot: TNode;
	private
		function GetLength: Integer;
		function GetNodeOfItem(AItem: P): PNode;
		function GetItemOfNode(ANode: PNode): P;
		function GetNextNode(ANode: PNode): PNode;
		procedure UnlinkNode(ANode: PNode);
		procedure InsertValueAfter(ANode: PNode; AValue: P);
		procedure LinkNodes(ANodeA, ANodeB: PNode);
		function GetFirst: P;
		function GetLast: P;
	public
		property Length: Integer read GetLength;
		property First: P read GetFirst;
		property Last: P read GetLast;
	public
		{constructor}procedure Init;
		{destructor}procedure Done;
		procedure Add(AItem: P);
		procedure Prepend(AItem: P);
		procedure Remove(AItem: P);
		procedure Clear;
		function GetNextItem(AItem: P): P;
		function GetEnumerator: TLinkedListEnumerator;
		function GetReversedEnumerator: TLinkedListReversedEnumerator;
	end;

	// dictionary

	{ TKeyAsHashManager }

	{ THashlessKeyManager }

	THashlessKeyManager = object
	public
		function GetKeyHash(const AKey): Dword; static; inline;
		function IsKeysEqual(const {%H-}KeyA, {%H-}KeyB): Boolean; static; inline;
		procedure CopyKey(out {%H-}Destination; const {%H-}Source); static; inline;
		procedure ClearKey(var {%H-}AKey); static; inline;
	end;

	{ GPTrue }

	GPTrue = class
		class function GetValue: Boolean; static;
	end;

	{ GPFalse }

	GPFalse = class
		class function GetValue: Boolean; static;
	end;

	generic TStringHashKeyManagerBase<TCloneKey, TCaseSensetive> = object
	public
		function GetKeyHash(const AKey: PChar): Dword; static; inline;
		function IsKeysEqual(const KeyA, KeyB: PChar): Boolean; static; inline;
		procedure CopyKey(out Destination: PChar; const Source: PChar); static; inline;
		procedure ClearKey(var AKey: PChar); static; inline;
	end;

    { TStringHashKeyManager }

	TStringHashKeyManager = specialize TStringHashKeyManagerBase<GPTrue, GPTrue>;
	TCaseInsensetiveStringHashKeyManager = specialize TStringHashKeyManagerBase<GPTrue, GPFalse>;
	TConstantStringHashKeyManager = specialize TStringHashKeyManagerBase<GPFalse, GPTrue>;

	generic THashKeyData<TKey> = object
	public type
		PHashKeyData = ^THashKeyData;
	public
		Hash: Dword;
		PageNode, ItemsNode: specialize TSLinkedNode<PHashKeyData>;
		Key: TKey;
	end;

	generic TSHashObject<TKey> = object
	public
		HashKeyData: specialize THashKeyData<TKey>;
	end;

	generic TSHashNode<TKey, TValue> = object (specialize TSHashObject<TKey>)
		Value: TValue;
	end;

	{ TSHashTable_VMT }

	TSHashTable_VMT = object
	public
		pDeleteItem: procedure (Item: Pointer); stdcall;
		pCreateItem: function (List: Pointer; ExtraSize: SizeUInt; ExtraFlags: Dword): Pointer; stdcall;
		pDelete: procedure (FreeMemory: Boolean); stdcall;
		pClear: procedure; stdcall;
	public
		function CreateItem(this: Pointer; List: Pointer; ExtraSize: SizeUInt; ExtraFlags: Dword): Pointer;
		procedure DeleteItem(this: Pointer; Item: Pointer);
	end;
	PSHashTable_VMT = ^TSHashTable_VMT;

	{ TSHashTable }

	generic TSHashTable<TKey, TValue, TKeyManager> = object
	private const
		PAGE_LIMIT = 12;
		MAX_PAGES_COUNT = 8192;
		INITIAL_PAGES_COUNT = 4;
	public type

		{ TItemsNodeOffset }

		TItemsNodeOffset = object
			class function GetValue: SizeUInt; static; inline;
		end;

		{ TPageNodeOffset }

		TPageNodeOffset = object
			class function GetValue: SizeUInt; static; inline;
		end;

		PValue = ^TValue;

		TItems = specialize TSLinkedList<TValue, TItemsNodeOffset>;
		PItems = ^TItems;

		TPage = specialize TSLinkedList<TValue, TPageNodeOffset>;
		PPage = ^TPage;

		TPageManager = specialize TArrayOfObjectsManager<TPage>;
		TPages = specialize TSGrowableArrayM<TPage, TPageManager>;
	public
		vtable: Pointer;
		Items: TItems;
		Counter: Dword;
		Pages: TPages;
		HashMask: Dword;
	private
		procedure InitPages;
		procedure Grow;
		procedure SetPagesCount(ACount: Dword);
		procedure Put(AValue: PValue);
	public
		function Find(const AKey: TKey; AHash: Dword; out AValue: PValue): Boolean;
		function Get(const AKey: TKey; AHash: Dword): PValue;
		function Find(const AKey: TKey; out AValue: PValue): Boolean;
		function Get(const AKey: TKey): PValue;
		procedure Put(const AKey: TKey; AValue: PValue);
		procedure FastPut(const AKey: TKey; AHash: Dword; AValue: PValue);
		function Remove(const AKey: TKey): Boolean;
		procedure Clear;
		function CreateItem(const AKey: TKey): PValue;
		function GetEnumerator: TItems.TLinkedListReversedEnumerator;
		{constructor} procedure Init;
		{destructor} procedure Done;
	public
		property ItemsByKey[const AKey: TKey]: PValue read Get; default;
	end;

implementation

{ TSLinkedList.TLinkedListReversedEnumerator }

constructor TSLinkedList.TLinkedListReversedEnumerator.Create(AList: PSLinkedList);
begin
	FList:= AList;
	Reset;
end;

function TSLinkedList.TLinkedListReversedEnumerator.GetCurrent: P;
begin
	Result:= FCurrent;
end;

function TSLinkedList.TLinkedListReversedEnumerator.MoveNext: Boolean;
begin
	FCurrent:= FCurrentNode^.Value;
	Result:= PtrInt(FCurrent) > 0;

	if Result then begin
		FCurrentNode:= FCurrentNode^.Previous;
	end;
end;

procedure TSLinkedList.TLinkedListReversedEnumerator.Reset;
begin
	FCurrent:= nil;
	FCurrentNode:= FList^.FRoot.Previous^.Previous;
end;

{ TMissingArrayItemManager }

procedure TMissingArrayItemManager.Initialize(out AItem; Size: SizeUInt);
begin
	raise Exception.Create('missing array item manager');
end;

procedure TMissingArrayItemManager.Finalize(out AItem; Size: SizeUInt);
begin
	raise Exception.Create('missing array item manager');
end;

procedure TMissingArrayItemManager.Copy(out ADestination; const ASource;
	Size: SizeUInt);
begin
	raise Exception.Create('missing array item manager');
end;

{ TKeyAsHashManager }

function THashlessKeyManager.GetKeyHash(const AKey): Dword;
begin
	Result:= PDword(@AKey)^;
end;

function THashlessKeyManager.IsKeysEqual(const KeyA, KeyB): Boolean;
begin
	Result:= True;
end;

procedure THashlessKeyManager.CopyKey(out Destination; const Source);
begin

end;

procedure THashlessKeyManager.ClearKey(var AKey);
begin

end;

{ GPTrue }

class function GPTrue.GetValue: Boolean;
begin
	Result:= True;
end;

{ GPFalse }

class function GPFalse.GetValue: Boolean;
begin
	Result:= False;
end;

//{ TConstantStringHashKeyManager }
//
//function TConstantStringHashKeyManager.GetKeyHash(const AKey: PChar): Dword;
//begin
//	Result:= SStrHash32(AKey);
//end;
//
//function TConstantStringHashKeyManager.IsKeysEqual(const KeyA, KeyB: PChar
//	): Boolean;
//begin
//	Result:= (KeyA = KeyB) or (StrComp(KeyA, KeyB) = 0);
//end;
//
//procedure TConstantStringHashKeyManager.CopyKey(out Destination: PChar;
//	const Source: PChar);
//begin
//	Destination:= Source;
//end;
//
//procedure TConstantStringHashKeyManager.ClearKey(var AKey: PChar);
//begin
//	AKey:= nil;
//end;

{ TStringHashKeyManager }

function TStringHashKeyManagerBase.GetKeyHash(const AKey: PChar): Dword;
begin
	Result:= SStrHash32(AKey);
end;

function TStringHashKeyManagerBase.IsKeysEqual(const KeyA, KeyB: PChar): Boolean;
begin
	if (not TCloneKey.GetValue) and (KeyA = KeyB) then begin
		Exit(True);
	end;

	if TCaseSensetive.GetValue then begin
		Result:= StrComp(KeyA, KeyB) = 0;
	end
	else begin
		Result:= StrIComp(KeyA, KeyB) = 0;
	end;
end;

procedure TStringHashKeyManagerBase.CopyKey(out Destination: PChar;
	const Source: PChar);
begin
	if TCloneKey.GetValue then begin
		Destination:= wc3memory.CloneString(Source);
	end
	else begin
		Destination:= Source;
	end;
end;

procedure TStringHashKeyManagerBase.ClearKey(var AKey: PChar);
begin
	if TCloneKey.GetValue then begin
		wc3memory.Free(AKey);
	end;
	AKey:= nil;
end;

{ TSHashTable_VMT }

function TSHashTable_VMT.CreateItem(this: Pointer; List: Pointer;
	ExtraSize: SizeUInt; ExtraFlags: Dword): Pointer;
begin
	asm mov ecx, this end;
	Result:= pCreateItem(List, ExtraSize, ExtraFlags);
end;

procedure TSHashTable_VMT.DeleteItem(this: Pointer; Item: Pointer);
begin
	asm mov ecx, this end;
	pDeleteItem(Item);
end;

{ TSHashTable.TItemsNodeOffset }

class function TSHashTable.TItemsNodeOffset.GetValue: SizeUInt;
begin
	Result:= SizeUInt(@PValue(nil)^.HashKeyData.ItemsNode);
end;

{ TSHashTable.TPageNodeOffset }

class function TSHashTable.TPageNodeOffset.GetValue: SizeUInt;
begin
	Result:= SizeUInt(@PValue(nil)^.HashKeyData.PageNode);
end;

{ TSLinkedNode }

function TSLinkedNode.IsLinked: Boolean;
begin
	Result:= Previous <> nil;
end;

procedure TSLinkedNode.Clear;
begin
	Previous:= nil;
	Value:= nil;
end;

procedure TSLinkedNode.Lock;
begin
	Previous:= @Self;
	Value:= P(not PtrUInt(@Self));
end;

{ TSGrowableArray }

{constructor}procedure TSGrowableArrayM.Init;
begin
	inherited;
	FGrowFactor:= 0;
end;

{ TMissingInitialOffset }

class function TMissingInitialOffset.{%H-}GetValue: SizeUInt;
begin
	raise Exception.Create('Attempt to init incorrect linked list.');
end;

{ TArrayOfObjectsManager }

procedure TArrayOfObjectsManager.Initialize(out AItem: TItem; Size: SizeUInt);
begin
	AItem.Init;
end;

procedure TArrayOfObjectsManager.Finalize(out AItem: TItem; Size: SizeUInt);
begin
	AItem.Done;
end;

procedure TArrayOfObjectsManager.Copy(out ADestination: TItem;
	const ASource: TItem; Size: SizeUInt);
begin
	ADestination:= ASource;
end;

{ TSArray.TArrayItemPointers }

function TSArrayM.TArrayItemPointers.GetItem(AIndex: Dword): P;
begin
	Result:= @FOwner^.FItems[AIndex];
end;

constructor TSArrayM.TArrayItemPointers.Init(AOwner: PSArray);
begin
	FOwner:= AOwner;
end;

function TSArrayM.TArrayItemPointers.GetEnumerator: TArrayItemPointersEnumerator;
begin
	Result.Init(FOwner);
end;

{ TSArray.TArrayItemPointers.TArrayItemPointersEnumerator }

{constructor}procedure TSArrayM.TArrayItemPointers.TArrayItemPointersEnumerator.Init(
	AOwner: PSArray);
begin
	FOwner:= AOwner;
	Reset;
end;

function TSArrayM.TArrayItemPointers.TArrayItemPointersEnumerator.GetCurrent: P;
begin
	Result:= @FOwner^.FItems[FCurrentIndex];
end;

function TSArrayM.TArrayItemPointers.TArrayItemPointersEnumerator.MoveNext: Boolean;
begin
	Inc(FCurrentIndex);
	Result:= FCurrentIndex < FOwner^.Length;
end;

procedure TSArrayM.TArrayItemPointers.TArrayItemPointersEnumerator.Reset;
begin
	FCurrentIndex:= Dword(-1);
end;

{ TDefaultArrayItemManager }

procedure TDefaultArrayItemManager.Initialize(out AItem; Size: SizeUInt);
begin

end;

procedure TDefaultArrayItemManager.Finalize(out AItem; Size: SizeUInt);
begin

end;

procedure TDefaultArrayItemManager.Copy(out ADestination; const ASource; Size: SizeUInt);
begin
	Move(ASource, {%H-}ADestination, Size);
end;

{ TSArray }

procedure TSArrayM.SetLength(ALength: Dword);
var
	i: Dword;
	First, Last: Dword;
begin
	if ALength < FLength then begin
		First:= ALength;
		Last:= FLength - 1;
		for i:= First to Last do begin
			TItemManager.Finalize(FItems[i], SizeOf(T));
		end;
	end;

	if ALength > Capacity then
		Capacity:= ALength;

	if ALength > FLength then begin
		First:= FLength;
		Last:= ALength - 1;
		for i:= First to Last do begin
			TItemManager.Initialize(FItems[i], SizeOf(T));
		end;
	end;

	FLength:= ALength;
end;

procedure TSArrayM.SetCapacity(ACapacity: Dword);
var
	BufferSize: SizeUInt;
begin
    if ACapacity <> FCapacity then begin
		if ACapacity < Length then
			Length:= ACapacity;

		BufferSize:= ACapacity * SizeUInt(SizeOf(T));

		if FItems = nil then
			FItems:= wc3memory.Allocate(BufferSize)
		else
			FItems:= wc3memory.ReAllocate(FItems, BufferSize);

		FCapacity:= ACapacity;
	end;
end;

function TSArrayM.GetItem(AIndex: Dword): T;
begin
	if AIndex < FLength then
		Result:= Self.FItems[AIndex]
	else
		raise ERangeError.CreateFmt('index %d out of range', [AIndex]);
end;

procedure TSArrayM.SetItem(AIndex: Dword; const AValue: T);
begin
	TItemManager.Copy(FItems[AIndex], AValue, SizeOf(T));
end;

function TSArrayM.GetItemPointers: TArrayItemPointers;
begin
	Result.Init(@Self);
end;

{constructor}procedure TSArrayM.Init;
begin
	FCapacity:= 0;
	FLength:= 0;
	FItems:= nil;
end;

{destructor}procedure TSArrayM.Done;
begin
	Capacity:= 0;
end;

function TSArrayM.Add(AValue: T): Dword;
begin
	Result:= Length;
	Length:= Length + 1;
	FItems[Result]:= AValue;
end;

function TSArrayM.GetNewItem: P;
begin
	Length:= Length + 1;
	Result:= ItemPointers[Length-1];
end;

function TSArrayM.Pop: T;
begin
	if Length = 0 then
		raise Exception.Create('list is empty');

	Result:= Self[Length-1];
	Length:= Length - 1;
end;

function TSArrayM.GetEnumerator: TArrayEnumerator;
begin
	Result:= TArrayEnumerator.Create(@Self);
end;

{ TSArray.TArrayEnumerator }

constructor TSArrayM.TArrayEnumerator.Create(AArray: PSArray);
begin
	FArray:= AArray;
	Reset;
end;

function TSArrayM.TArrayEnumerator.GetCurrent: T;
begin
	Result:= FArray^.Items[FCurrent];
end;

function TSArrayM.TArrayEnumerator.MoveNext: Boolean;
begin
	Inc(FCurrent);
	Result:= FCurrent < FArray^.Length;
end;

procedure TSArrayM.TArrayEnumerator.Reset;
begin
	FCurrent:= Dword(-1);
end;

{ TSLinkedList }

function TSLinkedList.GetLength: Integer;
var
	Item: P;
begin
	Result:= 0;
	for Item in Self do
		Inc(Result);
end;

function TSLinkedList.GetNodeOfItem(AItem: P): PNode;
begin
	Result:= PNode(Pointer(AItem) + FOffset);
end;

function TSLinkedList.GetItemOfNode(ANode: PNode): P;
begin
	Result:= P(Pointer(ANode) - FOffset);
end;

function TSLinkedList.GetNextNode(ANode: PNode): PNode;
begin
	if {%H-}PtrInt(ANode^.Value) > 0 then
		Result:= GetNodeOfItem(ANode^.Value)
	else
		Result:= PNode(not PtrUInt(ANode^.Value));
end;

procedure TSLinkedList.UnlinkNode(ANode: PNode);
begin
	if ANode^.Linked then begin
		ANode^.Previous^.Value:= ANode^.Value;
		GetNextNode(ANode)^.Previous:= ANode^.Previous;
	end;
	ANode^.Clear;
end;

procedure TSLinkedList.InsertValueAfter(ANode: PNode; AValue: P);
var
	NewNode: PNode;
begin
	NewNode:= GetNodeOfItem(AValue);
	NewNode^.Previous:= ANode;
	NewNode^.Value:= ANode^.Value;

	ANode^.Value:= AValue;
	GetNextNode(NewNode)^.Previous:= NewNode;
end;

procedure TSLinkedList.LinkNodes(ANodeA, ANodeB: PNode);
begin
	ANodeA^.Previous:= ANodeB;
	ANodeB^.Value:= GetItemOfNode(ANodeA);
end;

function TSLinkedList.GetFirst: P;
begin
	Result:= FRoot.Value;
	if {%H-}PtrInt(Result) <= 0 then
		Result:= nil;
end;

function TSLinkedList.GetLast: P;
begin
	Result:= FRoot.Previous^.Previous^.Value;
	if {%H-}PtrInt(Result) <= 0 then
		Result:= nil;
end;

{constructor}procedure TSLinkedList.Init;
begin
	FOffset:= TInitialOffset.GetValue;
	FRoot.Lock;
end;

{destructor}procedure TSLinkedList.Done;
begin
	Clear;
end;

procedure TSLinkedList.Add(AItem: P);
begin
	UnlinkNode(GetNodeOfItem(AItem));
	InsertValueAfter(FRoot.Previous, AItem);
end;

procedure TSLinkedList.Prepend(AItem: P);
begin
	UnlinkNode(GetNodeOfItem(AItem));
	InsertValueAfter(@FRoot, AItem);
end;

procedure TSLinkedList.Remove(AItem: P);
begin
	UnlinkNode(GetNodeOfItem(AItem));
end;

procedure TSLinkedList.Clear;
var
	Current, Next: PNode;
begin
	Current:= FRoot.Previous;
	while Current <> @FRoot do begin
		Next:= Current^.Previous;
		Current^.Clear;
		Current:= Next;
	end;
	FRoot.Lock;
end;

function TSLinkedList.GetNextItem(AItem: P): P;
begin
	Result:= GetNodeOfItem(AItem)^.Value;
	if PtrInt(Result) <= 0 then Result:= nil;
end;

function TSLinkedList.GetEnumerator: TLinkedListEnumerator;
begin
	Result:= TLinkedListEnumerator.Create(@Self);
end;

function TSLinkedList.GetReversedEnumerator: TLinkedListReversedEnumerator;
begin
	Result:= TLinkedListReversedEnumerator.Create(@Self);
end;

{ TSLinkedList.TLinkedListEnumerator }

constructor TSLinkedList.TLinkedListEnumerator.Create(AList: PSLinkedList);
begin
	FList:= AList;
	Reset;
end;

function TSLinkedList.TLinkedListEnumerator.GetEnumerator: TLinkedListEnumerator;
begin
	Result:= Self;
end;

function TSLinkedList.TLinkedListEnumerator.GetCurrent: P;
begin
	Result:= FCurrent;
end;

function TSLinkedList.TLinkedListEnumerator.MoveNext: Boolean;
begin
	FCurrent:= FCurrentNode^.Value;
	Result:= {%H-}PtrInt(FCurrent) > 0;

	if Result then begin
		FCurrentNode:= FList^.GetNodeOfItem(FCurrent);
	end;
end;

procedure TSLinkedList.TLinkedListEnumerator.Reset;
begin
	FCurrent:= nil;
	FCurrentNode:= @FList^.FRoot;
end;

{ TSHashTable }

procedure TSHashTable.InitPages;
begin
	Pages.Length:= INITIAL_PAGES_COUNT;
	HashMask:= Pages.Length - 1;
end;

procedure TSHashTable.Grow;
begin
	if Pages.Length < MAX_PAGES_COUNT then begin
		SetPagesCount(Pages.Length * 2);
	end;
end;

procedure TSHashTable.SetPagesCount(ACount: Dword);
var
	Page: PPage;
	Item: PValue;
	Index: Dword;
begin
	// Copying linked list causes nodes to point to wrong memory locations.
	// Destroy and recreate from scratch.
	Pages.Length:= 0;
	Pages.Length:= ACount;
	HashMask:= Pages.Length - 1;

	for Item in Items do begin
		Index:= Item^.HashKeyData.Hash and HashMask;
		Page:= Pages.ItemPointers[Index];
		Page^.Add(Item);
	end;
end;

function TSHashTable.Find(const AKey: TKey; AHash: Dword; out AValue: PValue): Boolean;
var
	Index: Integer;
	Item: PValue;
begin
	AValue:= nil;
	Result:= False;

	if HashMask = Dword(-1) then exit;
	Index:= AHash and HashMask;

	for Item in Pages[Index] do begin
		if (Item^.HashKeyData.Hash = AHash) and
			TKeyManager.IsKeysEqual(Item^.HashKeyData.Key, AKey)
		then begin
			AValue:= Item;
			Result:= True;
			break;
		end;
	end;
end;

function TSHashTable.Get(const AKey: TKey; AHash: Dword): PValue;
begin
	if not Find(AKey, AHash, Result) then
		raise Exception.Create('key error');
end;

function TSHashTable.Find(const AKey: TKey; out AValue: PValue): Boolean;
var
	Hash: Dword;
begin
	Hash:= TKeyManager.GetKeyHash(AKey);
	Result:= Find(AKey, Hash, AValue);
end;

function TSHashTable.Get(const AKey: TKey): PValue;
var
	Hash: Dword;
begin
	Hash:= TKeyManager.GetKeyHash(AKey);
	Result:= Get(AKey, Hash);
end;

procedure TSHashTable.Put(AValue: PValue);
var
	Index: Dword;
begin
	Items.Add(AValue);

	if HashMask = Dword(-1) then
		InitPages;

	Index:= AValue^.HashKeyData.Hash and HashMask;
	Pages.ItemPointers[Index]^.Add(AValue);

	if Pages[Index].Length > PAGE_LIMIT then
		Grow;
end;

procedure TSHashTable.Put(const AKey: TKey; AValue: PValue);
begin
	AValue^.HashKeyData.Hash:= TKeyManager.GetKeyHash(AKey);
	TKeyManager.CopyKey(AValue^.HashKeyData.Key, AKey);
	Put(AValue);
end;

procedure TSHashTable.FastPut(const AKey: TKey; AHash: Dword; AValue: PValue);
var
	Index: Dword;
begin
	AValue^.HashKeyData.Hash:= AHash; // TKeyManager.GetKeyHash(AKey);
	TKeyManager.CopyKey(AValue^.HashKeyData.Key, AKey);

	Items.Add(AValue);

	if HashMask = Dword(-1) then
		InitPages;

	Index:= AValue^.HashKeyData.Hash and HashMask;
	Pages.ItemPointers[Index]^.Add(AValue);

	//if Pages[Index].Length > PAGE_LIMIT then
	//	Grow;
end;

function TSHashTable.Remove(const AKey: TKey): Boolean;
var
	Hash: Dword;
	Index: Integer;
	Page: PPage;
	Item: PValue;
begin
	Result:= False;

	Hash:= TKeyManager.GetKeyHash(AKey);
	Index:= Hash and HashMask;

	if Index > Pages.Length-1 then
		Exit;

	Page:= Pages.ItemPointers[Index];

	for Item in Page^ do begin
		if (Item^.HashKeyData.Hash = Hash) and
			TKeyManager.IsKeysEqual(Item^.HashKeyData.Key, AKey)
		then begin
			Items.Remove(Item);
			Page^.Remove(Item);
			PSHashTable_VMT(vtable)^.DeleteItem(@Self, Item);

			Result:= True;
			break;
		end;
	end;
end;

procedure TSHashTable.Clear;
var
	Page: PPage;
begin
	Items.Clear;

	for Page in Pages.ItemPointers do begin
		Page^.Clear;
	end;
end;

function TSHashTable.CreateItem(const AKey: TKey): PValue;
begin
	Result:= PSHashTable_VMT(vtable)^.CreateItem(@Self, {omg}@Items, 0, 0);
	Put(AKey, Result);
end;

function TSHashTable.GetEnumerator: TItems.TLinkedListReversedEnumerator;
begin
	Result:= Items.GetReversedEnumerator;
end;

procedure TSHashTable.Init;
begin
	vtable:= nil; // TODO: сделать свою таблицу
	Items.Init;
	Counter:= 0;
	Pages.Init;
	HashMask:= Dword(-1);
end;

procedure TSHashTable.Done;
begin
	Items.Done;
	Pages.Done;
end;

end.

