unit modulesutil;

{$mode ObjFPC}{$H+}
{$WARN 4055 off : Conversion between ordinals and pointers is not portable}
interface

uses
	SysUtils, JwaWindows, ArrayList, errors, readstring;

type
	TModuleEntry32WArray = specialize TComparelessArray<TModuleEntry32W>;

	{ TModuleEnumerator }

	TModuleEnumerator = class
	private
		FProcessId: Dword;
		FSnapModule: Handle;
		FCurrent, FNext: TModuleEntry32W;
		FHasNext: Boolean;
	public
		function GetCurrent: TModuleEntry32W;
		function MoveNext: Boolean;
		procedure Reset;
		property Current: TModuleEntry32W read GetCurrent;
	public
		constructor Create(AProcessId: Dword);
		destructor Destroy; override;
	end;

	{ TProcessModules }

	TProcessModules = object
	private
		FProcessId: Dword;
	public
		function Collect: TModuleEntry32WArray;
		constructor Init(AProcessId: Dword);
		function GetEnumerator: TModuleEnumerator;
	end;

function Modules(ProcId: Dword): TProcessModules;
function GetModule(ProcId: dword; LibName: String; out Module: TModuleEntry32W): Boolean;
function GetModule(ProcId: dword; LibName: String): TModuleEntry32W;
function GetModuleHandleEx(ProcId: dword; LibName: String): Handle;
function GetProcAddressEx(Process: Handle; ModuleBase: Pointer; ProcName: String): Pointer;
function GetLibraryFunction(LibraryName, FunctionName: String): Pointer;
function GetModulePath(ProcessID: Dword; hModule: Handle): String;
function GetModulePath(hModule: Handle): String;

implementation

function Modules(ProcId: Dword): TProcessModules;
begin
	Result.Init(ProcId);
end;

function GetModule(ProcId: dword; LibName: String; out Module: TModuleEntry32W
	): Boolean;
var
	LocalModule: TModuleEntry32W;
	LibNameUnicode: UnicodeString;
begin
	Result:= False;

	LibNameUnicode:= UnicodeString(LibName);

	for LocalModule in Modules(ProcId) do begin
		if stricomp(@LocalModule.szModule[0], PWideChar(LibNameUnicode)) = 0 then begin
			Module:= LocalModule;
			Result:= True;
			break;
		end;
	end;
end;

function GetModule(ProcId: dword; LibName: String): TModuleEntry32W;
begin
	if not GetModule(ProcId, LibName, Result) then
		raise EFileNotFoundException.CreateFmt('Module "%s" not found.', [LibName]);
end;

function GetModuleHandleEx(ProcId: dword; LibName: String): Handle;
var
	Module: TModuleEntry32W;
begin
	Result:= 0;

	if GetModule(ProcId, LibName, Module) then begin
		Result:= Module.hModule;
	end;
end;

function GetProcAddressEx(Process: Handle; ModuleBase: Pointer; ProcName: String): Pointer;
var
	DosHeader: TImageDosHeader;
	pHeader: Pointer;
	Headers32: TImageNtHeaders32;
	Headers64: TImageNtHeaders64;
	ExportDir: TImageExportDirectory;
	Names: array of PChar = nil;
	Ordinals: array of Word = nil;
	Name: String;
	pDirectory, pArraySlot: Pointer;
	Offset: SizeUInt;
	i: Integer;
begin
	Result:= nil;

	if not ReadProcessMemory(Process, ModuleBase, @DosHeader, SizeOf(DosHeader), nil) then exit;
	if DosHeader.e_magic <> IMAGE_DOS_SIGNATURE then exit;

	pHeader:= ModuleBase + DosHeader.e_lfanew;
	if not ReadProcessMemory(Process, pHeader, @Headers32, SizeOf(Headers32), nil) then exit;

	case Headers32.OptionalHeader.Magic of
		IMAGE_NT_OPTIONAL_HDR32_MAGIC: begin
			if not ReadProcessMemory(Process, pHeader, @Headers32, SizeOf(Headers32), nil) then exit;
			pDirectory:= ModuleBase + Headers32.OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_EXPORT].VirtualAddress;
			if not ReadProcessMemory(Process, pDirectory, @ExportDir, SizeOf(ExportDir), nil) then exit;
		end;
		IMAGE_NT_OPTIONAL_HDR64_MAGIC: begin
			if not ReadProcessMemory(Process, pHeader, @Headers64, SizeOf(Headers64), nil) then exit;
			pDirectory:= ModuleBase + Headers64.OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_EXPORT].VirtualAddress;
			if not ReadProcessMemory(Process, pDirectory, @ExportDir, SizeOf(ExportDir), nil) then exit;
		end;
		else exit;
	end;

	SetLength(Names, ExportDir.NumberOfNames);
	if not ReadProcessMemory(Process, ModuleBase + ExportDir.AddressOfNames, @Names[0], Length(Names) * SizeOf(PChar), nil) then exit;

	SetLength(Ordinals, ExportDir.NumberOfNames);
	if not ReadProcessMemory(Process, ModuleBase + ExportDir.AddressOfNameOrdinals, @Ordinals[0], Length(Ordinals) * SizeOf(Word), nil) then exit;

	for i:= 0 to High(Names) do begin
		try
			Name:= ReadProcessString(Process, ModuleBase + SizeUInt(Names[i]));
		except
			break;
		end;

		if Name = ProcName then begin
			pArraySlot:= ModuleBase + ExportDir.AddressOfFunctions + Ordinals[i] * SizeOf(Pointer);
			if not ReadProcessMemory(Process, pArraySlot, @Offset, SizeOf(Offset), nil) then exit;
			Result:= ModuleBase + Offset;
			break;
		end;
	end;
end;

function GetLibraryFunction(LibraryName, FunctionName: String): Pointer;
var
	hLibrary: HMODULE;
begin
	hLibrary:= GetModuleHandleW(PWideChar(Unicodestring(LibraryName)));
	if hLibrary = 0 then
		RaiseLastOSError('Failed to find module "%s".', [LibraryName]);

	Result:= GetProcAddress(hLibrary, PAnsiChar(FunctionName));
	if Result = nil then
		RaiseLastOSError('Failed to find "%s" function of module "%s".', [FunctionName, LibraryName]);
end;

function GetModulePath(ProcessID: Dword; hModule: Handle): String;
var
	hProcess: Handle;
	Buffer: array [0..MAX_PATH-1+1] of WideChar;
	CopiedCount: Integer;
begin
	hProcess:= OpenProcess(PROCESS_QUERY_INFORMATION or PROCESS_VM_READ, False, ProcessID);
	if hProcess = INVALID_HANDLE_VALUE then
		RaiseLastOSError('Failed to open process.');

	CopiedCount:= GetModuleFileNameExW(
		hProcess,
		hModule,
		@Buffer[0],
		Length(Buffer)
	);
	if (CopiedCount > 0) and (CopiedCount < Length(Buffer)) then begin
		Buffer[CopiedCount]:= #0; // Windows XP support.
		Result:= {%H-}PWideChar(@Buffer[0]);
	end
	else begin
		raise Exception.Create('Failed to retrieve module file name.');
	end;
end;

function GetModulePath(hModule: Handle): String;
begin
	Result:= GetModulePath(GetCurrentProcessId(), hModule);
end;

{ TProcessModules }

function TProcessModules.Collect: TModuleEntry32WArray;
var
	ModuleEntry: TModuleEntry32W;
begin
	for ModuleEntry in Self do begin
		Result.Add(ModuleEntry);
	end;
end;

constructor TProcessModules.Init(AProcessId: Dword);
begin
	FProcessId:= AProcessId;
end;

function TProcessModules.GetEnumerator: TModuleEnumerator;
begin
	Result:= TModuleEnumerator.Create(FProcessId);
end;

{ TModuleEnumerator }

function TModuleEnumerator.GetCurrent: TModuleEntry32W;
begin
	Result:= FCurrent;
end;

function TModuleEnumerator.MoveNext: Boolean;
begin
	Result:= False;

	if FHasNext then begin
		FCurrent:= FNext;
		FHasNext:= Module32NextW(FSnapModule, FNext);
		Result:= True;
	end;
end;

procedure TModuleEnumerator.Reset;
begin
	ZeroMemory(@FNext, SizeOf(TModuleEntry32W));
	FNext.dwSize:= SizeOf(TModuleEntry32W);
	FHasNext:= Module32FirstW(FSnapModule, FNext);
end;

constructor TModuleEnumerator.Create(AProcessId: Dword);
begin
	FProcessId:= AProcessId;

	FSnapModule:= CreateToolhelp32Snapshot(
		TH32CS_SNAPMODULE + TH32CS_SNAPMODULE32,
		FProcessId
	);
	if FSnapModule = INVALID_HANDLE_VALUE
		then RaiseLastOSError('Failed to access list of loaded modules.');

	Reset;
end;

destructor TModuleEnumerator.Destroy;
begin
	CloseHandle(FSnapModule);
	inherited Destroy;
end;

end.

