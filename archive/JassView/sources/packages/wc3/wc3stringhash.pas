unit wc3stringhash;

{$mode objfpc}{$H+}

interface

uses
	Classes, SysUtils;

const
	STORM_NAME = 'storm.dll';

function SStrHash64(const AString: PChar; CaseSensetive: Boolean; InitialHash: Int64): Int64; stdcall; external STORM_NAME index 580;
function SStrHash32(const AString: PChar): Dword; stdcall; external STORM_NAME index 590;

implementation

end.

