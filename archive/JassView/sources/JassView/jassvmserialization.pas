unit JassVMSerialization;

{$mode ObjFPC}{$H+}

interface

uses
	Classes, SysUtils,
	ArrayList,
	JassVM,
	wc3jassvm;

const
	JASS_VM_DUMP_VERSION = 0;

procedure LoadJassVM(FilePath: String; JassVM: TJassVM);
procedure SaveJassVM(FilePath: String; JassVM: TJassVM);

implementation

const
	JASS_VM_DUMP_HEADER_MAGIC: QWord = $444D564A33524157; // WAR3JVMD

procedure LoadNative(Stream: TStream; Native: TNativeFunction);
begin
	Native.Name:= Stream.ReadAnsiString();
	Native.Signature:= Stream.ReadAnsiString();
	Dword(Native.Address):= Stream.ReadDWord();
end;

procedure SaveNative(Stream: TStream; Native: TNativeFunction);
begin
	Stream.WriteAnsiString(Native.Name);
	Stream.WriteAnsiString(Native.Signature);
	Stream.WriteDWord(Dword(Native.Address));
end;

procedure LoadNatives(Stream: TStream; Natives: TNativesMap);
var
	Count: Integer;
	i: Integer;
	Native: TNativeFunction;
begin
	Count:= Stream.ReadDWord();
	for i:= 0 to Count - 1 do begin
		Native:= TNativeFunction.Create();
		LoadNative(Stream, Native);
		Natives[Native.Name]:= Native;
	end;
end;

procedure SaveNatives(Stream: TStream; Natives: TNativesMap);
var
	i: Integer;
begin
	Stream.WriteDWord(Natives.Count);
	for i:= 0 to Natives.Count - 1 do begin
		SaveNative(Stream, Natives.Data[i]);
	end;
end;

procedure LoadInstructions(Stream: TStream; out Instructions: TInstructions);
begin
	with Instructions do begin
		Count:= Stream.ReadDWord();
		Stream.ReadBuffer(FItems[0], Count * SizeOf(TInstruction));
	end;
end;

procedure SaveInstructions(Stream: TStream; const Instructions: TInstructions);
begin
	with Instructions do begin
		Stream.WriteDWord(Count);
		Stream.WriteBuffer(FItems[0], Count * SizeOf(TInstruction));
	end;
end;

procedure LoadStrings(Stream: TStream; out Strings: TStringsArray);
var
	i: Integer;
begin
	Strings.Count:= Stream.ReadDWord();
	for i:= 0 to Strings.Count - 1 do begin
		Strings[i]:= Stream.ReadAnsiString();
	end;
end;

procedure SaveStrings(Stream: TStream; const Strings: TStringsArray);
var
	i: Integer;
begin
	Stream.WriteDWord(Strings.Count);
	for i:= 0 to Strings.Count - 1 do begin
		Stream.WriteAnsiString(Strings[i]);
	end;
end;

procedure LoadScript(Stream: TStream; Script: TScript);
begin
	Script.Handle:= Stream.ReadDWord();
	LoadInstructions(Stream, Script.Instructions);
	LoadStrings(Stream, Script.Strings);
end;

procedure SaveScript(Stream: TStream; Script: TScript);
begin
	Stream.WriteDWord(Script.Handle);
	SaveInstructions(Stream, Script.Instructions);
	SaveStrings(Stream, Script.Strings);
end;

procedure LoadScripts(Stream: TStream; Scripts: TScriptsMap);
var
	Count: Integer;
	i: Integer;
	id: Integer;
	Script: TScript;
begin
	Count:= Stream.ReadDWord();
	for i:= 0 to Count - 1 do begin
		Script:= TScript.Create();
		LoadScript(Stream, Script);
		Scripts[Script.Handle]:= Script;
	end;
end;

procedure SaveScripts(Stream: TStream; Scripts: TScriptsMap);
var
	i: Integer;
begin
	with Scripts do begin
		Stream.WriteDWord(Count);
		for i:= 0 to Count - 1 do begin
			SaveScript(Stream, Data[i]);
		end;
	end;
end;

procedure LoadMyScriptData(Stream: TStream; out ScriptData: TMyScriptData);
begin
	ScriptData.DataType:= TScriptDataType(Stream.ReadDWord());
	ScriptData.Initialized:= Boolean(Stream.ReadByte());
	ScriptData.Value:= Stream.ReadDWord();
end;

procedure SaveMyScriptData(Stream: TStream; const ScriptData: TMyScriptData);
begin
	Stream.WriteDWord(DWord(ScriptData.DataType));
	Stream.WriteByte(Byte(ScriptData.Initialized));
	Stream.WriteDWord(ScriptData.Value);
end;

procedure LoadVariables(Stream: TStream; Variables: TVariables);
var
	Count: Integer;
	i: Integer;
	Name: String;
	Variable: TMyScriptData;
begin
	Count:= Stream.ReadDWord();
	for i:= 0 to Count - 1 do begin
		Name:= Stream.ReadAnsiString();
		LoadMyScriptData(Stream, Variable);
		Variables[Name]:= Variable;
	end;
end;

procedure SaveVariables(Stream: TStream; Variables: TVariables);
var
	i: Integer;
begin
	with Variables do begin
		Stream.WriteDWord(Count);
		for i:= 0 to Count - 1 do begin
			Stream.WriteAnsiString(Keys[i]);
			SaveMyScriptData(Stream, Data[i]);
		end;
	end;
end;

procedure LoadFunction(Stream: TStream; Func: TFunction);
begin
	Func.Name:= Stream.ReadAnsiString();
	Func.Offset:= Stream.ReadDWord();
	Func.Size:= Stream.ReadDWord();
	Func.RetType:= TScriptDataType(Stream.ReadDWord());
end;

procedure SaveFunction(Stream: TStream; Func: TFunction);
begin
	Stream.WriteAnsiString(Func.Name);
	Stream.WriteDWord(Func.Offset);
	Stream.WriteDWord(Func.Size);
	Stream.WriteDWord(Dword(Func.RetType));
end;

function FunctionComparator(const A, B): Integer; cdecl;
var
	FunctionA: TFunction absolute A;
	FunctionB: TFunction absolute B;
begin
	Result:= FunctionA.Offset - FunctionB.Offset;
end;

procedure LoadFunctions(Stream: TStream; out Funcs: TFunctionsArray);
var
	i: Integer;
	Func: TFunction;
begin
	Funcs.Count:= Stream.ReadDWord();
	for i:= 0 to Funcs.Count - 1 do begin
		Func:= TFunction.Create();
		LoadFunction(Stream, Func);
		Funcs[i]:= Func;
	end;
	Funcs.Sort(@FunctionComparator);
end;

procedure SaveFunctions(Stream: TStream; const Funcs: TFunctionsArray);
var
	i: Integer;
begin
	Stream.WriteDWord(Funcs.Count);
	for i:= 0 to Funcs.Count - 1 do begin
		SaveFunction(Stream, Funcs[i]);
	end;
end;

procedure LoadMyScriptDataArray(Stream: TStream; out ScriptDataArray: TMyScriptDataArray);
var
	i: Integer;
begin
	ScriptDataArray.Count:= Stream.ReadDWord();
	for i:= 0 to ScriptDataArray.Count - 1 do begin
		LoadMyScriptData(Stream, ScriptDataArray.FItems[i]);
	end;
end;

procedure SaveMyScriptDataArray(Stream: TStream; const ScriptDataArray: TMyScriptDataArray);
var
	i: Integer;
begin
	Stream.WriteDWord(ScriptDataArray.Count);
	for i:= 0 to ScriptDataArray.Count - 1 do begin
		SaveMyScriptData(Stream, ScriptDataArray[i]);
	end;
end;

procedure LoadStackFrame(Stream: TStream; Frame: TStackFrame);
begin
	LoadVariables(Stream, Frame.Locals);
	LoadVariables(Stream, Frame.Arguments);
	LoadMyScriptDataArray(Stream, Frame.Stack);
end;

procedure SaveStackFrame(Stream: TStream; Frame: TStackFrame);
begin
	SaveVariables(Stream, Frame.Locals);
	SaveVariables(Stream, Frame.Arguments);
	SaveMyScriptDataArray(Stream, Frame.Stack);
end;

procedure LoadStackFrames(Stream: TStream; out Frames: TStackFrames);
var
	i: Integer;
	Frame: TStackFrame;
begin
	Frames.Count:= Stream.ReadDWord();
	for i:= 0 to Frames.Count - 1 do begin
		Frame:= TStackFrame.Create();
		LoadStackFrame(Stream, Frame);
		Frames[i]:= Frame;
	end;
end;

procedure SaveStackFrames(Stream: TStream; const Frames: TStackFrames);
var
	i: Integer;
begin
	Stream.WriteDWord(Frames.Count);
	for i:= 0 to Frames.Count - 1 do begin
		SaveStackFrame(Stream, Frames[i]);
	end;
end;

procedure LoadThread(Stream: TStream; Thread: TThread; Process: TProcess);
begin
	//Thread.Owner:= FindProcess(Stream.ReadDWord());
	Thread.Owner:= Process;
	Thread.Handle:= Stream.ReadDWord();
	LoadMyScriptDataArray(Stream, Thread.Registers);
	LoadStackFrames(Stream, Thread.Frames);
	Thread.Offset:= Stream.ReadDWord();
end;

procedure SaveThread(Stream: TStream; Thread: TThread);
begin
	//Stream.WriteDWord(Thread.Owner.Id);
	Stream.WriteDWord(Thread.Handle);
	SaveMyScriptDataArray(Stream, Thread.Registers);
	SaveStackFrames(Stream, Thread.Frames);
	Stream.WriteDWord(Thread.Offset);
end;

procedure LoadThreads(Stream: TStream; out Threads: TThreads; Process: TProcess);
var
	Count: Integer;
	i: Integer;
	Thread: TThread;
begin
	Count:= Stream.ReadDWord();
	for i:= 0 to Count - 1 do begin
		Thread:= TThread.Create();
		LoadThread(Stream, Thread, Process);
		Threads.Add(Thread);
	end;
end;

procedure SaveThreads(Stream: TStream; const Threads: TThreads);
var
	i: Integer;
begin
	Stream.WriteDWord(Threads.Count);
	for i:= 0 to Threads.Count - 1 do begin
		SaveThread(Stream, Threads[i]);
	end;
end;

procedure LoadProcess(Stream: TStream; Process: TProcess; JassVM: TJassVM);
begin
	with Process do begin
		hMainThread:= Stream.ReadDWord();
		LoadVariables(Stream, Globals);
		LoadFunctions(Stream, Functions);
		LoadStrings(Stream, Strings);
		Script:= JassVM.Scripts[Stream.ReadDWord()];
		LoadThreads(Stream, Threads, Process);
	end;
end;

procedure SaveProcess(Stream: TStream; Process: TProcess);
begin
	with Process do begin
		Stream.WriteDWord(hMainThread);
		SaveVariables(Stream, Globals);
		SaveFunctions(Stream, Functions);
		SaveStrings(Stream, Strings);
		Stream.WriteDWord(Script.Handle);
		SaveThreads(Stream, Threads);
	end;
end;

procedure LoadProcesses(Stream: TStream; out Processes: TProcesses; JassVM: TJassVM);
var
	Count: Integer;
	i: Integer;
	Process: TProcess;
begin
	Count:= Stream.ReadDWord();
	for i:= 0 to Count - 1 do begin
		Process:= TProcess.Create();
		LoadProcess(Stream, Process, JassVM);
		Processes.Add(Process);
	end;
end;

procedure SaveProcesses(Stream: TStream; const Processes: TProcesses);
var
	i: Integer;
begin
	Stream.WriteDWord(Processes.Count);
	for i:= 0 to Processes.Count - 1 do begin
		SaveProcess(Stream, Processes[i]);
	end;
end;

procedure LoadRunningThreadHandles(Stream: TStream; JassVM: TJassVM);
var
	Count: Integer;
	i: Integer;
	id: Integer;
begin
	Count:= Stream.ReadDWord();
	for i:= 0 to Count - 1 do begin
		id:= Stream.ReadDWord();
		JassVM.RunningThreads.Add(JassVM.FindThread(id));
	end;
end;

procedure SaveRunningThreadHandles(Stream: TStream; JassVM: TJassVM);
var
	i: Integer;
begin
	with JassVM.RunningThreads do begin
		Stream.WriteDWord(Count);
		for i:= 0 to Count - 1 do begin
			Stream.WriteDWord(Items[i].Handle);
		end;
	end;
end;

procedure LoadJassVM(FilePath: String; JassVM: TJassVM);
var
	Stream: TFileStream;
	Version: Integer;
begin
	Stream:= TFileStream.Create(FilePath, fmOpenRead);
	try
		if Stream.ReadQWord() <> JASS_VM_DUMP_HEADER_MAGIC
			then raise Exception.Create('Invalid dump file header.');

		Version:= Stream.ReadDWord();
		if Version > JASS_VM_DUMP_VERSION
			then raise Exception.CreateFmt(
				'The highest supported version is %s, but the input file has version %d.', [
					JASS_VM_DUMP_VERSION,
					Version
				]
			);

		LoadNatives(Stream, JassVM.Natives);
		LoadScripts(Stream, JassVM.Scripts);
		LoadProcesses(Stream, JassVM.Processes, JassVM);
		LoadRunningThreadHandles(Stream, JassVM);
	finally
		Stream.Destroy();
	end;
end;

procedure SaveJassVM(FilePath: String; JassVM: TJassVM);
var
	Stream: TFileStream;
begin
	Stream:= TFileStream.Create(FilePath, fmCreate);
	try
		Stream.WriteQWord(JASS_VM_DUMP_HEADER_MAGIC);
		Stream.WriteDWord(JASS_VM_DUMP_VERSION);
		SaveNatives(Stream, JassVM.Natives);
		SaveScripts(Stream, JassVM.Scripts);
		SaveProcesses(Stream, JassVM.Processes);
		SaveRunningThreadHandles(Stream, JassVM);
	finally
		Stream.Destroy();
	end;
end;

end.

