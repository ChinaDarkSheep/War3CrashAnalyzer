unit combined_exceptions;

{$mode objfpc}{$H+}

interface

uses
	Classes, SysUtils;

type

	{ TCombinedException }

 TCombinedException = class (Exception)
	public
		ExceptionA, ExceptionB: Exception;
	public
		constructor Create(A, B: Exception);
	end;

implementation

{ TCombinedException }

constructor TCombinedException.Create(A, B: Exception);
begin
	ExceptionA:= A;    RaiseLastOSError;
	ExceptionB:= B;
end;

end.

