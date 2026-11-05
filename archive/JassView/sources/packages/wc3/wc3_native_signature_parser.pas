unit wc3_native_signature_parser;

{$mode objfpc}{$H+}

interface

type
	TNativeFunctionArgumentType = record
		TypeId: Char;
		SubTypeName: String;
	end;
	PNativeFunctionArgumentType = ^TNativeFunctionArgumentType;

	TNativeFunctionSignature = record
		Arguments: array of TNativeFunctionArgumentType;
		ReturnType: TNativeFunctionArgumentType;
	end;
	PNativeFunctionSignature = ^TNativeFunctionSignature;

function ParseNativeFunctionSignature(
	Signature: String;
	out ParsedSignature: TNativeFunctionSignature;
	CheckFinished: Boolean
): Boolean;

implementation

uses
	SysUtils;

type
	TParserState = (
		psWaitingForArgumentsStart,
		psParsingArguments,
		psParsedArgument,
		psParsingType,
		psParsingSubTypeName,
		psParsingReturnType,
		psParsedReturnType,
		psFinished
	);

function NextChar(Text: String; var Position: Integer; out c: Char): Boolean;
begin
	Result:= False;

	if (Position >= 1) and (Position <= Length(Text)) then begin
		c:= Text[Position];
		Inc(Position);
		Result:= True;
	end;
end;

function ParseNativeFunctionSignature(
	Signature: String;
	out ParsedSignature: TNativeFunctionSignature;
	CheckFinished: Boolean
): Boolean;
var
	State: TParserState = psWaitingForArgumentsStart;
	StateToEnterAfterWorkDone: TParserState;
	Position: Integer = 1;
	CurrentChar: Char;
	CurrentType: TNativeFunctionArgumentType;
	SubTypeNameBuilder: TStringBuilder;
begin
	Result:= False;

	StateToEnterAfterWorkDone:= psFinished;
	ParsedSignature.Arguments:= nil;
	CurrentChar:= '?';
	CurrentType.TypeId:= '?';
	CurrentType.SubTypeName:= '';

	SubTypeNameBuilder:= TStringBuilder.Create();

	while True do begin
		case State of
			psWaitingForArgumentsStart:
			begin
				if not NextChar(Signature, Position, CurrentChar) then
					Break;

				if CurrentChar = '(' then
					State:= psParsingArguments
				else
					Break;
			end;

			psParsingArguments:
			begin
				if not NextChar(Signature, Position, CurrentChar) then
					Break;

				if CurrentChar = ')' then begin
					State:= psParsingReturnType;
				end
				else begin
					Dec(Position); // put type letter back
					State:= psParsingType;
					StateToEnterAfterWorkDone:= psParsedArgument;
				end;
			end;

			psParsedArgument:
			begin
				with ParsedSignature do begin
					SetLength(Arguments, Length(Arguments)+1);
					Arguments[High(Arguments)]:= CurrentType;
				end;

				State:= psParsingArguments;
			end;

			psParsingType:
			begin
				if not NextChar(Signature, Position, CurrentChar) then
					Break;

				CurrentType.TypeId:= CurrentChar;
				CurrentType.SubTypeName:= '';

				if CurrentChar = 'H' then begin
					SubTypeNameBuilder.Clear;
					State:= psParsingSubTypeName;
					StateToEnterAfterWorkDone:= StateToEnterAfterWorkDone;
				end
				else
					State:= StateToEnterAfterWorkDone;
			end;

			psParsingSubTypeName:
			begin
				if not NextChar(Signature, Position, CurrentChar) then
					Break;

				if CurrentChar = ';' then begin
					CurrentType.SubTypeName:= SubTypeNameBuilder.ToString;
					State:= StateToEnterAfterWorkDone;
				end
				else
					SubTypeNameBuilder.Append(CurrentChar);
			end;

			psParsingReturnType:
			begin
				State:= psParsingType;
				StateToEnterAfterWorkDone:= psParsedReturnType;
			end;

			psParsedReturnType:
			begin
				ParsedSignature.ReturnType:= CurrentType;
				State:= psFinished;
			end;

			psFinished:
			begin
				if CheckFinished
					then Result:= Position > Length(Signature)
					else Result:= True;

				Break;
			end;
		end;
	end;

	SubTypeNameBuilder.Free;
end;

end.

