unit wc3nettag;

{$mode objfpc}{$H+}

interface

type
	{ TNetTag }

	TNetTag = object
		Presence: Dword;
		Birth: Dword;
	end;
	PNetTag = ^TNetTag;

implementation

end.

