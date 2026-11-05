unit injection;

{$mode objfpc}{$H+}
{$WARN 4055 off : Conversion between ordinals and pointers is not portable}
interface

uses
	SysUtils, hooks, errors, modulesutil, jwaWindows;

procedure InjectLibrary(Process: Handle; ModulePath: String; Timeout: Dword = 10000);

implementation

procedure InjectLibrary(Process: Handle; ModulePath: String; Timeout: Dword);
var
	ProcessId: Dword;
	uModulePath: Unicodestring;
	ExecutableMemory: Pointer;
	BytesWritten: DWORD;
	hThread: Handle = INVALID_HANDLE_VALUE;
	pKernel32Base, pfLoadLibraryW, pfGetLastError: Pointer;
	ExitCode: Dword;
	NameLen: Dword;
	Inject: packed record
		push: Byte; pLibraryName: Dword;
		call1: Byte; pLoadLibrary: Dword;
		test_eax_eax: Word;
		jnz: Word;
		call2: Byte; pGetLastError: Dword;
		ret: Byte; ret_bytes: Word;
		xor_eax_eax: word;
		ret2: Byte; ret_bytes2: Word;
	end;
	WaitResult: Dword;
begin
	ProcessId:= GetProcessID(Process);
	uModulePath:= Unicodestring(ModulePath);
	NameLen:= Length(uModulePath)*2+2;

	ExecutableMemory:= VirtualAllocEx(Process, nil, SizeOf(Inject) + NameLen, MEM_COMMIT, PAGE_EXECUTE_READ);
	if ExecutableMemory = nil then RaiseLastOSError('Failed to allocate memory in target process.');

	try
		pKernel32Base:= GetModule(ProcessId, 'kernel32.dll').modBaseAddr;
		if pKernel32Base = nil then raise Exception.Create('Failed to find "kernel32.dll" in target process.');

		pfLoadLibraryW:= GetProcAddressEx(Process, pKernel32Base, 'LoadLibraryW');
		if pfLoadLibraryW = nil then raise Exception.Create('Failed to find "LoadLibraryW" function in target process.');

		pfGetLastError:= GetProcAddressEx(Process, pKernel32Base, 'GetLastError');
		if pfGetLastError = nil then raise Exception.Create('Failed to find "GetLastError" function in target process.');

		with Inject do begin
			push:= $68;
			pLibraryName:= {%H-}SizeUInt(ExecutableMemory + SizeOf(Inject));
			call1:= $E8;
			test_eax_eax:= $C085;
			jnz:= $0875;
			pLoadLibrary:= CalcJumpOffset(pfLoadLibraryW, Pointer(ExecutableMemory) + (@call1 - Pointer(@Inject)));
			call2:= $E8;
			pGetLastError:= CalcJumpOffset(pfGetLastError, Pointer(ExecutableMemory) + (@call2 - Pointer(@Inject)));
			ret:= $C2;
			ret_bytes:= 4;
			xor_eax_eax:= $C031;
			ret2:= $C2;
			ret_bytes2:= 4;
		end;

		if not WriteProcessMemory(Process, Pointer(ExecutableMemory), @Inject, SizeOf(Inject), @BytesWritten) then
			RaiseLastOSError('Failed to rewrite target process memory. (1)');

		if BytesWritten <> SizeOf(Inject) then
			RaiseLastOSError('Failed to rewrite target process memory. (2)');

		if not WriteProcessMemory(Process, Pointer(ExecutableMemory + SizeOf(Inject)), @uModulePath[1], NameLen, @BytesWritten) then
			RaiseLastOSError('Failed to rewrite target process memory. (3)');

		if BytesWritten <> NameLen then
			RaiseLastOSError('Failed to rewrite target process memory. (4)');

		if not FlushInstructionCache(Process, ExecutableMemory, SizeOf(Inject)) then
			RaiseLastOSError('Failed to flush instruction cache.');

		hThread:= CreateRemoteThread(Process, nil, 0, TThreadStartRoutine(ExecutableMemory), nil, 0, nil);
		if hThread = 0 then
			RaiseLastOSError('Failed to create thread in target process.');

		WaitResult:= WaitForSingleObject(hThread, Timeout);
		case WaitResult of
			WAIT_OBJECT_0: {all ok};
			WAIT_FAILED: RaiseLastOSError('Waiting for the loader thread to complete failed.');
			WAIT_TIMEOUT: RaiseLastOSError('Loader thread timed out.');
			else RaiseLastOSError(Format('WaitForSingleObject returned unknown error code: %d.', [WaitResult]));
		end;

		if not GetExitCodeThread(hThread, ExitCode{%H-}) then
			RaiseLastOSError('Failed to retrieve loader thread exit code.');

		if ExitCode <> ERROR_SUCCESS then
			RaiseLastOSError('Loader thread finished with error code.', ExitCode);
	finally
		VirtualFreeEx(Process, Pointer(ExecutableMemory), SizeOf(Inject) + NameLen, MEM_RELEASE);
		CloseHandle(hThread);
	end;
end;

end.

