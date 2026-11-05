unit wc3float;

{$mode objfpc}{$H+}
{$asmmode intel}

interface

uses
	wc3main;

const
	DEFAULT_EPSILON: Single = 0.001;

type

	{ TFloatWar3 }

	TFloatWar3 = object
	public
		Value: Single;
	public
		function IsApproximatelyEqualTo(const AOther: TFloatWar3; Epsilon: Single = 0.001): Boolean;
		function Abs: TFloatWar3;
	end;
	PFloatWar3 = ^TFloatWar3;

operator + (const A, B: TFloatWar3): TFloatWar3;
operator - (const A, B: TFloatWar3): TFloatWar3;
operator - (const A: TFloatWar3): TFloatWar3;
operator * (const A, B: TFloatWar3): TFloatWar3;
operator / (const A, B: TFloatWar3): TFloatWar3;
operator > (const A, B: TFloatWar3): Boolean;
operator >= (const A, B: TFloatWar3): Boolean;
operator < (const A, B: TFloatWar3): Boolean;
operator <= (const A, B: TFloatWar3): Boolean;
operator = (const A, B: TFloatWar3): Boolean;

operator explicit (const A: Int32): TFloatWar3;
operator explicit (const A: Single): TFloatWar3;
operator explicit (const A: TFloatWar3): Single;

implementation

type
	//TFloatOperation = function ({out dst: TFloatWar3; constref a: TFloatWar3} constref b: TFloatWar3): PFloatWar3; stdcall; // fastcall
	TFloatOperation = function (Dummy: Pointer; constref a: Single; out dst: Single; constref b: Single): PSingle; register;
	//TIntToFloat = function ({out dst: TFloatWar3; value: Int32}): PFloatWar3; // fastcall
	TIntToFloat = function (Dummy: Pointer; Value: Int32; out Result: TFloatWar3): PFloatWar3; register; // fastcall

var
	_FloatAdd, _FloatSub, _FloatMul, _FloatDiv: TFloatOperation;
	_IntToFloat: TIntToFloat;

//function DoFloatOperation(f: TFloatOperation; const a, b: TFloatWar3): TFloatWar3;
//var
//	MyResult: Single;
//	pa, pb: PFloatWar3;
//begin
//	pa:= @a;
//	pb:= @b;
//	asm
//		lea ecx, MyResult
//		mov edx, pa
//		mov eax, pb
//		push eax
//		call f
//	end ['ecx', 'edx', 'eax'];
//
//	Result.Value:= MyResult;
//end;

function DoFloatOperation(f: TFloatOperation; const a, b: TFloatWar3): TFloatWar3; inline;
begin
	f(nil, a.Value, Result.Value, b.Value);
end;

operator + (const A, B: TFloatWar3): TFloatWar3;
begin
	Result:= DoFloatOperation(_FloatAdd, a, b);
end;

operator - (const A, B: TFloatWar3): TFloatWar3;
begin
	Result:= DoFloatOperation(_FloatSub, a, b);
end;

operator-(const A: TFloatWar3): TFloatWar3;
begin
	Result.Value:= -A.Value;
end;

operator * (const A, B: TFloatWar3): TFloatWar3;
begin
	Result:= DoFloatOperation(_FloatMul, a, b);
end;

operator / (const A, B: TFloatWar3): TFloatWar3;
begin
	Result:= DoFloatOperation(_FloatDiv, a, b);
end;

operator > (const A, B: TFloatWar3): Boolean;
begin
	Result:= A.Value > B.Value;
end;

operator >= (const A, B: TFloatWar3): Boolean;
begin
	Result:= A.Value >= B.Value;
end;

operator < (const A, B: TFloatWar3): Boolean;
begin
	Result:= A.Value < B.Value;
end;

operator <= (const A, B: TFloatWar3): Boolean;
begin
	Result:= A.Value <= B.Value;
end;

operator = (const A, B: TFloatWar3): Boolean;
begin
	Result:= A.Value = B.Value;
end;

operator explicit(const A: Int32): TFloatWar3;
begin
	_IntToFloat(nil, A, Result);
end;

operator explicit(const A: Single): TFloatWar3;
begin
	Result.Value:= A;
end;

operator explicit(const A: TFloatWar3): Single;
begin
	Result:= A.Value;
end;

{ TFloatWar3 }

function TFloatWar3.IsApproximatelyEqualTo(const AOther: TFloatWar3;
	Epsilon: Single): Boolean;
begin
	Result:= (Self - AOther).Abs().Value <= epsilon;
end;

function TFloatWar3.Abs: TFloatWar3;
begin
	Dword(Result.Value):= PDword(@Value)^ and $7FFFFFFF;
end;

procedure OnInit;
begin
	Pointer(_FloatAdd):= Pointer(GameDll + $6EF000);
	Pointer(_FloatSub):= Pointer(GameDll + $6EEEF0);
	Pointer(_FloatMul):= Pointer(GameDll + $6EEE20);
	Pointer(_FloatDiv):= Pointer(GameDll + $6EFE10);
	Pointer(_IntToFloat):= Pointer(GameDll + $6EF350);
end;

initialization
	wc3main.SubscribeOnInit(@OnInit);

end.


