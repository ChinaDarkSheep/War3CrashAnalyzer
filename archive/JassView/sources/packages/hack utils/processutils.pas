unit ProcessUtils;

{$mode ObjFPC}{$H+}
interface

uses
	SysUtils, JwaWindows, ArrayList, errors;

type
	TProcessEntry32WArray = specialize TComparelessArray<TProcessEntry32W>;

	{ TProcessEnumerator }

	TProcessEnumerator = class
	private
		FSnapModule: Handle;
		FCurrent, FNext: TProcessEntry32W;
		FHasNext: Boolean;
	public
		function GetCurrent: TProcessEntry32W;
		function MoveNext: Boolean;
		procedure Reset;
		property Current: TProcessEntry32W read GetCurrent;
	public
		constructor Create();
		destructor Destroy; override;
	end;

	{ TProcesses }

	TProcesses = object
	public
		function Collect: TProcessEntry32WArray;
		function GetEnumerator: TProcessEnumerator;
	end;

function Processes: TProcesses;

implementation

function Processes: TProcesses;
begin
	Result:= Default(TProcesses);
end;

{ TProcesses }

function TProcesses.Collect: TProcessEntry32WArray;
var
	ProcessEntry: TProcessEntry32W;
begin
	for ProcessEntry in Self do begin
		Result.Add(ProcessEntry);
	end;
end;

function TProcesses.GetEnumerator: TProcessEnumerator;
begin
	Result:= TProcessEnumerator.Create();
end;

{ TProcessEnumerator }

function TProcessEnumerator.GetCurrent: TProcessEntry32W;
begin
	Result:= FCurrent;
end;

function TProcessEnumerator.MoveNext: Boolean;
begin
	Result:= False;

	if FHasNext then begin
		FCurrent:= FNext;
		FHasNext:= Process32NextW(FSnapModule, FNext);
		Result:= True;
	end;
end;

procedure TProcessEnumerator.Reset;
begin
	ZeroMemory(@FNext, SizeOf(TProcessEntry32W));
	FNext.dwSize:= SizeOf(TProcessEntry32W);
	FHasNext:= Process32FirstW(FSnapModule, FNext);
end;

constructor TProcessEnumerator.Create();
begin
	FSnapModule:= CreateToolhelp32Snapshot(
		TH32CS_SNAPPROCESS,
		0
	);
	if FSnapModule = INVALID_HANDLE_VALUE
		then RaiseLastOSError('Failed to access list of processes.');

	Reset;
end;

destructor TProcessEnumerator.Destroy;
begin
	CloseHandle(FSnapModule);
	inherited Destroy;
end;

end.

