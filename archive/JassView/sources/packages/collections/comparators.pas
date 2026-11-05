unit comparators;

{$mode objfpc}{$H+}
{$ModeSwitch AdvancedRecords}

interface

type
	{ TComparable }

	generic TComparable<T, TComparator> = record
	public
		Value: T;
	public
		class operator < (const A,B: TComparable): Boolean;
		class operator > (const A,B: TComparable): Boolean;
		class operator = (const A,B: TComparable): Boolean;
		class operator := (const A: TComparable): T;
		class operator := (const A: T): TComparable;
	end;

	{ TPointerComparator }

	generic TPointerComparator<T> = object
		class function IsLess (const A, B: T): Boolean; static;
		class function IsGreater (const A, B: T): Boolean; static;
		class function IsEqual (const A, B: T): Boolean; static;
	end;

	{ TMemoryComparator }

	generic TMemoryComparator<T> = object
		class function IsLess (const A, B: T): Boolean; static;
		class function IsGreater (const A, B: T): Boolean; static;
		class function IsEqual (const A, B: T): Boolean; static;
	end;

	{ TValueComparator }

	generic TValueComparator<T> = object
		class function IsLess (const A, B: T): Boolean; static;
		class function IsGreater (const A, B: T): Boolean; static;
		class function IsEqual (const A, B: T): Boolean; static;
	end;

implementation

{ TValueComparator }

class function TValueComparator.IsLess(const A, B: T): Boolean;
begin
	Result:= A < B;
end;

class function TValueComparator.IsGreater(const A, B: T): Boolean;
begin
	Result:= A > B;
end;

class function TValueComparator.IsEqual(const A, B: T): Boolean;
begin
	Result:= A = B;
end;

{ TComparable }

class operator TComparable.<(const A, B: TComparable): Boolean;
begin
	Result:= TComparator.IsLess(A, B);
end;

class operator TComparable.>(const A, B: TComparable): Boolean;
begin
	Result:= TComparator.IsGreater(A, B);
end;

class operator TComparable.=(const A, B: TComparable): Boolean;
begin
	Result:= TComparator.IsEqual(A, B);
end;

class operator TComparable.:=(const A: TComparable): T;
begin
	Result:= A.Value;
end;

class operator TComparable.:=(const A: T): TComparable;
begin
	Result.Value:= A;
end;

{ TPointerComparator }

class function TPointerComparator.IsLess(const A, B: T): Boolean;
begin
	Result:= @A < @B;
end;

class function TPointerComparator.IsGreater(const A, B: T): Boolean;
begin
	Result:= @A > @B;
end;

class function TPointerComparator.IsEqual(const A, B: T): Boolean;
begin
	Result:= @A = @B;
end;

{ TMemoryComparator }

class function TMemoryComparator.IsLess(const A, B: T): Boolean;
begin
	Result:= CompareByte(A, B, SizeOf(T)) < 0;
end;

class function TMemoryComparator.IsGreater(const A, B: T): Boolean;
begin
	Result:= CompareByte(A, B, SizeOf(T)) > 0;
end;

class function TMemoryComparator.IsEqual(const A, B: T): Boolean;
begin
	Result:= CompareByte(A, B, SizeOf(T)) = 0;
end;

end.

