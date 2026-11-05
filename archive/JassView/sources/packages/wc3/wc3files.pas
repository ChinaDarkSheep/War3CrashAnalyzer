unit wc3files;

{$mode objfpc}{$H+}

interface

uses
	Windows,
	Classes, SysUtils;

const
  INVALID_FILE_SIZE = Handle(-1);

function OpenArchive(FileName: PChar; Priority, Flags: Dword; out hMpq: Handle): LongBool; stdcall; external 'Storm.dll' index 266;
function OpenFile(hMpq: Handle; FileName: PChar; SearchScope: Dword; out hFile: Handle): LongBool; stdcall; external 'Storm.dll' index 268;
function ReadFile(hFile: Handle; Buffer: Pointer; Size: Dword; out BytesReaded: Dword; Overlapped: POverlapped = nil): LongBool; stdcall; external 'Storm.dll' index 269;
function ReadFile(hFile: Handle; Buffer: Pointer; Size: Dword; BytesReaded: PDword = nil; Overlapped: POverlapped = nil): LongBool; stdcall; external 'Storm.dll' index 269;
function GetFileSize(hFile: Handle; out FileSize: Dword): Dword; stdcall; external 'Storm.dll' index 265;
function GetFileSize(hFile: Handle; FileSize: PDword = nil): Dword; stdcall; external 'Storm.dll' index 265;
function CloseArchive(hMpq: Handle): LongBool; stdcall; external 'Storm.dll' index 252;
function CloseFile(hFile: Handle): LongBool; stdcall; external 'Storm.dll' index 253;

function SFileGetPath(hFile: Handle; Buffer: Pointer; MaxCount: Dword): LongBool; stdcall; external 'Storm.dll' index 275;
function SFileExists(FilePath: PChar): LongBool; stdcall; external 'Storm.dll' index 288;

function SFileGetPath(hFile: Handle): String;

function ReadFile(hMpq: Handle; FileName: String; out Bytes: TBytes; SearchScope: Dword = 0): Boolean;
function ReadFile(hMpq: Handle; FileName: String; Stream: TStream; SearchScope: Dword = 0): Boolean;
function ReadFile(hMpq: Handle; FileName: String; out Content: String; SearchScope: Dword = 0): Boolean;

function ReadBytes(FilePath: String): TBytes;
function ReadText(FilePath: String): String;
procedure UnpackFile(StoredFilePath, DstPath: String);

implementation

function SFileGetPath(hFile: Handle): String;
var
	Buffer: array [0..MAX_PATH-1] of Char;
begin
	Buffer[0]:= #0;
	SFileGetPath(hFile, @Buffer, Length(Buffer));
	Result:= Buffer;
end;

function ReadFile(hMpq: Handle; FileName: String; out Bytes: TBytes; SearchScope: Dword = 0): Boolean;
var
  hFile: Handle;
  FileSize: Dword;
begin
	Result:= false;

	if OpenFile(hMpq, PChar(FileName), SearchScope, hFile) then
	try
		FileSize:= GetFileSize(hFile);

		if FileSize <> INVALID_FILE_SIZE then begin
			SetLength(Bytes, FileSize);
			Result:= ReadFile(hFile, @Bytes[0], Length(Bytes));
		end;
	finally
		CloseFile(hFile);
	end;
end;

function ReadFile(hMpq: Handle; FileName: String; Stream: TStream; SearchScope: Dword = 0): Boolean;
var
  Buffer: TBytes;
	Position: Int64;
begin
	Result:= false;
	Position:= Stream.Position;

	if ReadFile(hMpq, FileName, Buffer, SearchScope) then begin
		Stream.Write(Buffer[0], Length(Buffer));
		Stream.Position:= Position;
		Result:= true;
	end;
end;

function ReadFile(hMpq: Handle; FileName: String; out Content: String; SearchScope: Dword): Boolean;
var
	Buffer: TBytes;
begin
	Result:= False;
	Content:= '';

	if ReadFile(hMpq, FileName, Buffer, SearchScope) then begin
		SetLength(Content, Length(Buffer));
		Move(Buffer[0], Content[1], Length(Buffer));
		Result:= True;
	end;
end;

function ReadBytes(FilePath: String): TBytes;
begin
    if not ReadFile(0, FilePath, Result) then
		raise Exception.CreateFmt('Failed to read file: "%s".', [FilePath]);
end;

function ReadText(FilePath: String): String;
begin
	if not ReadFile(0, FilePath, Result) then
		raise Exception.CreateFmt('Failed to read file: "%s".', [FilePath]);
end;

procedure UnpackFile(StoredFilePath, DstPath: String);
var
	Stream: TMemoryStream;
begin
	Stream:= TMemoryStream.Create;

	try
		if not ReadFile(0, StoredFilePath, Stream) then
			raise Exception.CreateFmt('Failed to read file: "%s".', [StoredFilePath]);

		Stream.SaveToFile(DstPath);
	finally
		Stream.Free;
	end;
end;

end.













