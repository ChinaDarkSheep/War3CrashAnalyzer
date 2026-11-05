unit readstring;

{$mode objfpc}{$H+}

interface

uses
	Windows, Classes, SysUtils;

function ReadProcessString(Process: Handle; Address: Pointer; EndMarker: String = #0; BufferSize: SizeUInt = 4096): String;

implementation

procedure AddCharsToString(var s: String; chars: array of Char);
begin
	s += Chars;
end;

function ReadProcessString(Process: Handle; Address: Pointer; EndMarker: String; BufferSize: SizeUInt): String;
const
	PAGE_SIZE = 4096;
var
	CurrentAddress: Pointer;
	OffsetInPage, PageRemainingBytes: SizeUInt;
	Buffer: array of Char = nil;
	BytesRead: Dword;
	i, MarkerPosition, CharsMatched, CharsToDelete: SizeUInt;
	MarkerFound: Boolean;
begin
	Result:= '';
	CharsMatched:= 0;
	MarkerFound:= False;
	SetLength(Buffer, BufferSize);
	CurrentAddress:= Address;

	while not MarkerFound do begin
		OffsetInPage:= SizeUInt(CurrentAddress) mod PAGE_SIZE;
		PageRemainingBytes:= PAGE_SIZE - OffsetInPage;
		if not ReadProcessMemory(
			Process,
			CurrentAddress,
			@Buffer[0],
			Min(PageRemainingBytes, Length(Buffer)),
			@BytesRead
		) then
			if GetLastError <> ERROR_PARTIAL_COPY then
				RaiseLastOSError;

		for i:= 1 to BytesRead do begin
			if Buffer[i-1] = EndMarker[CharsMatched+1] then begin
				Inc(CharsMatched);

				if CharsMatched {%H-}= Length(EndMarker) then begin
					MarkerFound:= True;

                    if i {%H-}< Length(EndMarker) then
						CharsToDelete:= Length(EndMarker) - i
					else begin
						CharsToDelete:= 0;
						MarkerPosition:= i - Length(EndMarker) + 1;
					end;

					break;
				end;
			end;
		end;

		if MarkerFound then begin
			if CharsToDelete > 0 then begin
				Result:= Result[1..Length(Result) - CharsToDelete];
			end
			else begin
				if MarkerPosition > 1 then
					AddCharsToString(Result, Buffer[0..MarkerPosition-1-1]);
			end;
		end
		else begin
			AddCharsToString(Result, Buffer[0..BytesRead-1]);
		end;

		CurrentAddress += BytesRead;
	end;
end;

end.

