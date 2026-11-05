unit hooks;

{$mode objfpc}{$H+}
{$ASMMODE INTEL}
{$WARN 7098 off : No size specified and unable to determine the size of the operands, using DWORD as default}
interface

uses
	SysUtils,
	Windows;

type
	TBytes = array of Byte;
	PBytes = ^TBytes;

function CalcJumpOffset(dst,src: Pointer): PtrUInt;
function WriteJumpAtAddress(Process: Handle; src,dst: Pointer; OriginalBytes: PBytes = nil): Boolean;
function WriteCallAtAddress(Process: Handle; src,dst: Pointer): Boolean;
function WriteCallAtAddress(Process: Handle; src,dst: Pointer; out OldDst: Pointer): Boolean;
function Hook(OrigFunc, HookFunc: Pointer; out NewFunc: Pointer; OldBytes: PBytes = nil): Boolean;
procedure UnHook(OrigFunc, NewFunc: Pointer; OldBytes: PBytes);

implementation

type
	TJumpRecord = packed record
		Command: Byte;
		Offset: PtrUInt;
	end;
	PJumpRecord = ^TJumpRecord;

const
	ASM_CALL_FAR: Byte = $E8;
	ASM_JUMP_FAR: Byte = $E9;

//
// Копипаста
//

{$ifdef WIN32}
function OpCodeLength(Address: Pointer): Dword; cdecl; assembler;
const
  O_UNIQUE = 0;
  O_PREFIX = 1;
  O_IMM8 = 2;
  O_IMM16 = 3;
  O_IMM24 = 4;
  O_IMM32 = 5;
  O_IMM48 = 6;
  O_MODRM = 7;
  O_MODRM8 = 8;
  O_MODRM32 = 9;
  O_EXTENDED = 10;
  O_WEIRD = 11;
  O_ERROR = 12;
asm
  pushad
  cld
  xor edx, edx
  mov esi, Address
  mov ebp, esp
  push 1097F71Ch
  push 0F71C6780h
  push 17389718h
  push 101CB718h
  push 17302C17h
  push 18173017h
  push 0F715F547h
  push 4C103748h
  push 272CE7F7h
  push 0F7AC6087h
  push 1C121C52h
  push 7C10871Ch
  push 201C701Ch
  push 4767602Bh
  push 20211011h
  push 40121625h
  push 82872022h
  push 47201220h
  push 13101419h
  push 18271013h
  push 28858260h
  push 15124045h
  push 5016A0C7h
  push 28191812h
  push 0F2401812h
  push 19154127h
  push 50F0F011h
  mov ecx, 15124710h
  push ecx
  push 11151247h
  push 10111512h
  push 47101115h
  mov eax, 12472015h
  push eax
  push eax
  push 12471A10h
  add cl, 10h
  push ecx
  sub cl, 20h
  push ecx
  xor ecx, ecx
  dec ecx
@@ps:
  inc  ecx
  mov  edi, esp
@@go:
  lodsb
  mov  bh, al
@@ft:
  mov  ah, [edi]
  inc  edi
  shr  ah, 4
  sub  al, ah
  jnc  @@ft
  mov al, [edi-1]
  and al, 0Fh
  cmp  al, O_ERROR
  jnz  @@i7
  pop edx
  not edx
@@i7:
  inc edx
  cmp al, O_UNIQUE
  jz @@t_exit
  cmp al, O_PREFIX
  jz @@ps
  add  edi, 51h
  cmp  al, O_EXTENDED
  jz   @@go
  mov edi, [ebp+((1+8)*4)+4{%H-}]
@@i6:
  inc  edx
  cmp  al, O_IMM8
  jz   @@t_exit
  cmp  al, O_MODRM
  jz   @@t_modrm
  cmp  al, O_WEIRD
  jz   @@t_weird
@@i5:
  inc  edx
  cmp  al, O_IMM16
  jz   @@t_exit
  cmp  al, O_MODRM8
  jz   @@t_modrm
@@i4:
  inc  edx
  cmp  al, O_IMM24
  jz   @@t_exit
@@i3:
  inc  edx
@@i2:
  inc  edx
  pushad
  mov  al, 66h
  repnz scasb
  popad
  jnz  @@c32
@@d2:
  dec  edx
  dec  edx
@@c32:
  cmp  al, O_MODRM32
  jz   @@t_modrm
  sub  al, O_IMM32
  jz   @@t_imm32
@@i1:
  inc  edx
  @@t_exit:
  jmp @@ASMEnded
@@t_modrm:
  lodsb
  mov  ah, al
  shr  al, 7
  jb   @@prmk
  jz   @@prm
  add  dl, 4
  pushad
  mov  al, 67h
  repnz scasb
  popad
  jnz  @@prm
@@d3:  sub  dl, 3
  dec  al
@@prmk:jnz  @@t_exit
  inc  edx
  inc  eax
@@prm:
  and  ah, 00000111b
  pushad
  mov  al, 67h
  repnz scasb
  popad
  jz   @@prm67chk
  cmp  ah, 04h
  jz   @@prmsib
  cmp  ah, 05h
  jnz  @@t_exit
@@prm5chk:
  dec  al
  jz   @@t_exit
@@i42: add  dl, 4
  jmp  @@t_exit
@@prm67chk:
  cmp  ax, 0600h
  jnz  @@t_exit
  inc  edx
  jmp  @@i1
@@prmsib:
  cmp  al, 00h
  jnz  @@i1
  lodsb
  and  al, 00000111b
  sub  al, 05h
  jnz  @@i1
  inc  edx
  jmp  @@i42
@@t_weird:
  test byte ptr [esi], 00111000b
  jnz  @@t_modrm
  mov  al, O_MODRM8
  shr  bh, 1
  adc  al, 0
  jmp  @@i5
@@t_imm32:
  sub  bh, 0A0h
  cmp  bh, 04h
  jae  @@d2
  pushad
  mov  al, 67h
  repnz scasb
  popad
  jnz  @@chk66t
@@d4:  dec  edx
  dec  edx
@@chk66t:
  pushad
  mov  al, 66h
  repnz scasb
  popad
  jz   @@i1
  jnz  @@d2
@@ASMEnded:
  mov esp, ebp
  mov [result+(9*4)], edx
  popad
end;
{$else}
function OpCodeLength(Address: Pointer): Dword;
begin

end;
{$endif}

function CalcJumpOffset(dst,src: Pointer): PtrUInt;
begin
  Result:= PtrUInt(dst - src - SizeOf(TJumpRecord));
end;

function GetJumpDestination(src: Pointer; Offset: PtrUInt): Pointer;
begin
	Result:= src + SizeOf(TJumpRecord) + Offset;
end;

function WriteJumpAtAddress(Process: Handle; src, dst: Pointer;
	OriginalBytes: PBytes): Boolean;
var
	JumpRecord: TJumpRecord;
begin
	if OriginalBytes <> nil then begin
		SetLength(OriginalBytes^, SizeOf(TJumpRecord));
		ReadProcessMemory(Process, src, @OriginalBytes^[0], Length(OriginalBytes^), nil);
	end;

	JumpRecord.Command:= ASM_JUMP_FAR;
	JumpRecord.Offset:= CalcJumpOffset(dst,src);
	Result:= WriteProcessMemory(Process, src, @JumpRecord, SizeOf(TJumpRecord), nil);
end;

function WriteCallAtAddress(Process:Handle; src, dst:Pointer):Boolean;
var
  JumpRecord: TJumpRecord;
begin
  JumpRecord.Command:= ASM_CALL_FAR;
  JumpRecord.Offset:= CalcJumpOffset(dst,src);
  Result:= WriteProcessMemory(Process, src, @JumpRecord, SizeOf(TJumpRecord), nil);
end;

function WriteCallAtAddress(Process: Handle; src,dst: Pointer; out OldDst: Pointer): Boolean;
begin
	OldDst:= GetJumpDestination(src, PDword(src+1)^);
	Result:= WriteCallAtAddress(Process, src, dst);
end;

function Hook(OrigFunc, HookFunc: Pointer; out NewFunc: Pointer; OldBytes: PBytes): Boolean;
var
	i: Integer;
	OldProtect: Dword;
	TotalSize: SizeUInt;
	OpCodeLen: SizeUInt;
	DestAddr: Pointer;
	pJumpRec: PJumpRecord;
	NewFuncMem: Pointer;
begin
	Result:= False;

	if (OrigFunc = nil) or (HookFunc = nil) then exit;

	NewFuncMem:= VirtualAlloc(nil, $1000, MEM_COMMIT, PAGE_EXECUTE_READWRITE);
	if NewFuncMem = nil then exit;

	TotalSize:= 0;
	OpCodeLen:= 0;
	for i:= 1 to 5 do begin
		OpCodeLen:= OpCodeLength(OrigFunc+TotalSize);
		CopyMemory(NewFuncMem+TotalSize, OrigFunc+TotalSize, OpCodeLen);

		// Исправление относительных адресов для команд call и jmp (far)
		pJumpRec:= NewFuncMem + TotalSize;
		if pJumpRec^.Command in [ASM_JUMP_FAR,ASM_CALL_FAR] then begin
			DestAddr:= GetJumpDestination(OrigFunc+TotalSize, pJumpRec^.Offset);
			pJumpRec^.Offset:= CalcJumpOffset(DestAddr, NewFuncMem+TotalSize);
		end;

		TotalSize += OpCodeLen;
		if TotalSize >= SizeOf(TJumpRecord) then break;
	end;

	if OldBytes <> nil then begin
		SetLength(OldBytes^, TotalSize);
		CopyMemory(@OldBytes^[0], OrigFunc, TotalSize);
	end;

	if not VirtualProtect(OrigFunc, TotalSize, PAGE_EXECUTE_READWRITE, @OldProtect) then exit;

	if WriteJumpAtAddress(GetCurrentProcess,NewFuncMem+TotalSize,OrigFunc+TotalSize) = false then exit;
    FlushInstructionCache(GetCurrentProcess, NewFuncMem, TotalSize + SizeOf(TJumpRecord));

    if @NewFunc <> nil then NewFunc:= NewFuncMem;

	if WriteJumpAtAddress(GetCurrentProcess,OrigFunc,HookFunc) = false then exit;
    FlushInstructionCache(GetCurrentProcess, OrigFunc, TotalSize);

	VirtualProtect(OrigFunc, TotalSize, OldProtect, @OldProtect);

	Result:= True;
end;

procedure UnHook(OrigFunc, NewFunc: Pointer; OldBytes: PBytes);
begin
	if OldBytes <> nil then begin
		WriteProcessMemory(
			GetCurrentProcess,
			OrigFunc,
			@OldBytes^[0],
			Length(OldBytes^),
			PDword(nil)^
		);

		FlushInstructionCache(
			GetCurrentProcess,
			@OrigFunc,
			Length(OldBytes^)
		);
	end;

	VirtualFree(NewFunc, 0, MEM_FREE);
end;

end.

