unit wc3_chat_command;

{$mode objfpc}{$H+}
{$ASMMODE INTEL}

interface

uses
	Windows,
	fgl,
	hooks,
	wc3main;

type
	TOutputChatCallback = function (var Message: String): Boolean;
	TOutputChatCallbacks = specialize TFPGList<TOutputChatCallback>;

procedure SubscribeOnOutputChat(Callback: TOutputChatCallback);

implementation

var
	ChatInputHooked: Boolean = False;
	ChatInputCallbacks: TOutputChatCallbacks = nil;
	TempMessage: String;

	lorig_CChatBox_GetText: function: PChar;
	lorig_CChatEditBar_GetText: function: PChar;

procedure OnChatInput(var Message: PChar);
var
	Callback: TOutputChatCallback;
begin
	if (Message = nil) or (Message = '') then exit;
	TempMessage:= Message;

	for Callback in ChatInputCallbacks do begin
		if Callback(TempMessage) then begin
			break;
		end;
	end;

	Message:= PChar(TempMessage);
end;

function lhook_CChatBox_GetText: PChar;
begin
	Result:= lorig_CChatBox_GetText();
	OnChatInput(Result);
end;

function lhook_CChatEditBar_GetText: PChar;
begin
	Result:= lorig_CChatEditBar_GetText();
	OnChatInput(Result);
end;

procedure InitChatInputHook;
begin
	WriteCallAtAddress(GetCurrentProcess(), Pointer(GameDll + $5AF711), @lhook_CChatBox_GetText, Pointer(lorig_CChatBox_GetText));
	WriteCallAtAddress(GetCurrentProcess(), Pointer(GameDll + $2FC747), @lhook_CChatEditBar_GetText, Pointer(lorig_CChatEditBar_GetText));
end;

procedure SubscribeOnOutputChat(Callback: TOutputChatCallback);
begin
	if not ChatInputHooked then begin
		InitChatInputHook;
		ChatInputHooked:= True;
	end;

	if ChatInputCallbacks = nil then
		ChatInputCallbacks:= TOutputChatCallbacks.Create;

	ChatInputCallbacks.Add(Callback);
end;

end.




















