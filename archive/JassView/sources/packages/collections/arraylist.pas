unit ArrayList;

{$mode objfpc}{$H+}
{$ModeSwitch advancedrecords}
{$modeswitch typehelpers}

interface

uses
	Math, Classes;

type
	{ TComparelessArray }

	generic TComparelessArray<T> = object
	public type
		TItems = array of T;

		{ TArrayKosEnumerator }

		TArrayKosEnumerator = class
		private
			FItems: TItems;
			FPosition: Integer;
		public
			constructor Create(AItems: TItems);
			function GetCurrent: T;
			function MoveNext: Boolean;
			property Current: T read GetCurrent;
		end;

		TComparator = function (const A, B): Integer; cdecl;
		TFilterFunc = function (AItem: T): Boolean;

	public
		FItems: TItems;
	private
		function GetItem(Index: Integer): T;
		procedure SetItem(Index: Integer; Value: T);
		procedure SetCount(ACount: Integer);
		function GetCount: Integer;
		function ConvertIndex(Index: Integer): Integer;
	public
		property Count: Integer read GetCount write SetCount;
		property Items[Index: Integer]: T read GetItem write SetItem; default;
	public
		constructor Init;
		destructor Done;
		procedure Add(const Value: T);
		procedure AddAll(const Values: TComparelessArray);
		procedure AddAll(const Values: array of T);
		function GetDefault(Index: Integer; DefaultValue: T): T;
		function Delete(Index: Integer; SaveOrder: Boolean = False): TComparelessArray;
		procedure Clear;
		procedure InvertOrder;
		procedure Sort(Comparator: TComparator);
		procedure Filter(AFilterFunc: TFilterFunc);
		function Slice(First: Integer = 0; Last: Integer = -1): TComparelessArray;
		function Clone: TComparelessArray;
		function GetItems: TItems;
		function GetEnumerator: TArrayKosEnumerator;
	public {Syndrome}
		function contains_index(index:integer):boolean;
		function first_index:integer;
		function last_index:integer;
		function first_item:T;
		function last_item:T;
		function is_empty:boolean;
		procedure delete_last_item;
		procedure swap(a,b:integer);
		class function create(source:array of T): TComparelessArray; static;
	end;

    generic TArray<T> = object (specialize TComparelessArray<T>)
	private
		function IsItemsEqual(const A,B: T): Boolean;
	public
		function Delete(Index: Integer; SaveOrder: Boolean = False): TArray;
		function Slice(First: Integer = 0; Last: Integer = -1): TArray;
		function Clone: TArray;
		procedure Remove(const Value: T; SaveOrder: Boolean = False);
		function IndexOf(const Value: T): Integer;
		function Contains(const Value: T): Boolean;
	public {Syndrome}
		class function create(source:array of T): TArray; static;
	end;

	TBytesArray = specialize TArray<Byte>;
	TDwordsArray = specialize TArray<Dword>;
	TIntegersArray = specialize TArray<Integer>;
	TPointersArray = specialize TArray<Pointer>;
	THandleArray = specialize TArray<System.THandle>;
	array_of_utf8_strings = specialize TArray<UTF8String>;

	{ TStringsArray }

	TStringsArray = object (specialize TArray<String>)
	public
		function Join(Separator: String): String;
		procedure SaveToStream(AStream: TStream);
		procedure SaveToFile(AFilePath: String);
	end;

procedure qsort(
	var Items;
	Count: SizeUInt;
	ItemSize: SizeUInt;
	Comparator: TComparelessArray.TComparator
); cdecl; external 'msvcrt.dll';

implementation

{ TStringsArray }

function TStringsArray.Join(Separator: String): String;
var
	s: String;
begin
	Result:= '';

	for s in Self.Slice(0, -2) do begin
		Result += s + Separator;
	end;

	if Self.Count > 0 then Result += Self[-1];
end;

procedure TStringsArray.SaveToStream(AStream: TStream);
const
	ENDLINE: array [0..1] of Char = #13#10;
var
	s: String;
begin
	for s in Self do begin
		AStream.WriteBuffer(s[1], Length(s));
		AStream.WriteBuffer(ENDLINE, Length(ENDLINE));
	end;
end;

procedure TStringsArray.SaveToFile(AFilePath: String);
var
	Stream: TFileStream;
begin
	Stream:= TFileStream.Create(AFilePath, fmCreate);
	try
		SaveToStream(Stream);
	finally
		Stream.Free;
	end;
end;

{ TArray.TArrayEnumerator }

constructor TComparelessArray.TArrayKosEnumerator.Create(AItems: TItems);
begin
	FItems:= AItems;
	FPosition:= -1;
end;

function TComparelessArray.TArrayKosEnumerator.GetCurrent: T;
begin
	Result:= FItems[FPosition];
end;

function TComparelessArray.TArrayKosEnumerator.MoveNext: Boolean;
begin
	FPosition += 1;
	Result:= FPosition < Length(FItems);
end;

{ TComparelessArray }

function TComparelessArray.GetItem(Index: Integer): T;
begin
	Result:= FItems[ConvertIndex(Index)];
end;

procedure TComparelessArray.SetItem(Index: Integer; Value: T);
begin
	FItems[ConvertIndex(Index)]:= Value;
end;

procedure TComparelessArray.SetCount(ACount: Integer);
begin
	SetLength(FItems, ACount);
end;

function TComparelessArray.GetCount: Integer;
begin
	Result:= Length(FItems);
end;

function TComparelessArray.ConvertIndex(Index: Integer): Integer;
begin
	if Index < 0 then
		Result:= Count + Index
	else
		Result:= Index;
end;

constructor TComparelessArray.Init;
begin
	FItems:= nil;
end;

destructor TComparelessArray.Done;
begin

end;

procedure TComparelessArray.Add(const Value: T);
begin
	Count:= Count + 1;
	Self[-1]:= Value;
end;

procedure TComparelessArray.AddAll(const Values: TComparelessArray);
var
	NewChunkStart: Integer;
begin
	NewChunkStart:= Count;
	Count:= Count + Values.Count;

	Move(Values.FItems[0], FItems[NewChunkStart], Values.Count * SizeOf(T));
end;

procedure TComparelessArray.AddAll(const Values: array of T);
var
	Item: T;
begin
	for Item in Values do begin
		Self.Add(Item);
	end;
end;

function TComparelessArray.GetDefault(Index: Integer; DefaultValue: T): T;
begin
	Index:= ConvertIndex(Index);

	if InRange(Index, 0, Count - 1) then
		Result:= Self[Index]
	else
		Result:= DefaultValue;
end;

function TComparelessArray.Delete(Index: Integer; SaveOrder: Boolean):TComparelessArray;
var
	i: Integer;
begin
	if SaveOrder then begin
		for i:= ConvertIndex(Index) + 1 to Count - 1 do begin
			Self[i-1]:= Self[i];
		end;
	end
	else begin
		Self[Index]:= Self[-1];
	end;

	Count:= Count - 1;
	result:= self;
end;

procedure TComparelessArray.Clear;
begin
	Count:= 0;
end;

procedure TComparelessArray.InvertOrder;
var
	HalfCount, i: Integer;
	TempLeft, TempRight: T;
begin
	HalfCount:= Count div 2;

	for i:= 1 to HalfCount do begin
		TempLeft:= Self[i-1];
		TempRight:= Self[-i];

		Self[i-1]:= TempRight;
		Self[-i]:= TempLeft;
	end;
end;

procedure TComparelessArray.Sort(Comparator: TComparator);
begin
	qsort(FItems[0], Count, SizeOf(T), Comparator);
end;

procedure TComparelessArray.Filter(AFilterFunc: TFilterFunc);
var
	Filtered: TComparelessArray;
	Item: T;
begin
	Filtered.Clear;

	for Item in Self do begin
		if AFilterFunc(Item) then Filtered.Add(Item);
	end;

	Self.FItems:= Filtered.FItems;
end;

function TComparelessArray.Slice(First: Integer; Last: Integer): TComparelessArray;
var
	i: Integer;
begin
	Result.Init;

	First:= ConvertIndex(First);
	Last:= ConvertIndex(Last);

	if First > Last then exit;
	if First > (Count - 1) then exit;
	if Last < 0 then exit;

	Result.SetCount(Last - First + 1);

	for i:= First to Last do begin
		Result[i - First]:= Self[i];
	end;
end;

function TComparelessArray.Clone: TComparelessArray;
begin
	Result.Init;
	Result.AddAll(Self);
end;

function TComparelessArray.GetItems: TItems;
begin
	Result:= FItems;
end;

function TComparelessArray.GetEnumerator: TArrayKosEnumerator;
begin
	Result:= TArrayKosEnumerator.Create(FItems);
end;

{ syndrome }

function TComparelessArray.contains_index(index: integer): boolean;
begin
   result:= (self.first_index <= index) and (index <= self.last_index);
end;

function TComparelessArray.first_index: integer;
begin
   result:= 0;
end;

function TComparelessArray.last_index: integer;
begin
	result:= self.Count-1;
end;

function TComparelessArray.first_item: T;
begin
   result:= self[self.first_index];
end;

function TComparelessArray.last_item: T;
begin
   result:= self[self.last_index];
end;

function TComparelessArray.is_empty: boolean;
begin
    result:= self.count = 0;
end;


procedure TComparelessArray.delete_last_item;
begin
	self.delete(self.last_index);
end;

procedure TComparelessArray.swap(a, b: integer);
var
	c:T;
begin
	c:= self[a];
	self[a]:= self[b];
	self[b]:= c;
end;

class function TComparelessArray.create(source: array of T): TComparelessArray;
begin
   result.AddAll(source);
end;

{ TArray }

function TArray.IsItemsEqual(const A, B: T): Boolean;
begin
	Result:= A = B; //CompareByte(A, B, SizeOf(T)) = 0;
end;

function TArray.Delete(Index: Integer; SaveOrder: Boolean): TArray;
begin
	inherited Delete(Index, SaveOrder);
	Result:= Self;
end;

function TArray.Slice(First: Integer; Last: Integer): TArray;
begin
	Result:= TArray(inherited Slice(First, Last));
end;

function TArray.Clone: TArray;
begin
	Result:= TArray( inherited Clone() );
end;

procedure TArray.Remove(const Value: T; SaveOrder: Boolean);
var
	i: Integer;
begin
	for i:= Count - 1 downto 0 do begin
		if IsItemsEqual(Self[i], Value) then begin
			Delete(i, SaveOrder);
			Break;
		end;
	end;
end;

// FIXME: питонские индексы привели к проблеме
// если элемент не найден, то возвращать -1 уже неправильно.
function TArray.IndexOf(const Value: T): Integer;
var
	i: Integer;
begin
	for i:= 0 to Count-1 do begin
		if IsItemsEqual(Self[i], Value) then exit(i);
	end;

	Result:= -1;
end;

function TArray.Contains(const Value: T): Boolean;
begin
	Result:= IndexOf(Value) <> -1;
end;

{ syndrome }

class function TArray.create(source: array of T): TArray;
begin
	Result:= TArray( inherited create(source) );
end;

end.

