unit MainUnit;

{$mode objfpc}{$H+}

interface

uses
	JwaWindows,
	Classes, SysUtils, FileUtil, SynEdit, Math, Forms, Controls, Graphics, Dialogs,
	StdCtrls, ComCtrls, Grids, Menus, ExtCtrls,
	IniFiles,
	selectprocessdialogunit,
	wc3jassvm,
	wc3remote,
	ArrayList, modulesutil,
	jassvm, JassVMSerialization;

type

	TFunctionPointer = record
		FunctionIndex: Integer;
		InstructionIndex: SizeUInt;
	end;

	{ TMainForm }

	TMainForm = class(TForm)
	published
		gbRunningThreads: TGroupBox;
		gbFrames: TGroupBox;
		gbLocals: TGroupBox;
		gbFunctions: TGroupBox;
		gbParameters: TGroupBox;
		gbStack: TGroupBox;
		gbCode: TGroupBox;
		gbStacktrace: TGroupBox;
		gbCodeRightPanel: TGroupBox;
		lbStacktrace: TListBox;
		MainMenu1: TMainMenu;
		FileMenuItem: TMenuItem;
		ExitMenuItem: TMenuItem;
		HelpMenuItem: TMenuItem;
		AboutMenuItem: TMenuItem;
		OpenDialog: TOpenDialog;
		SaveDialog: TSaveDialog;
		SaveDumpMenuItem: TMenuItem;
		LoadDumpMenuItem: TMenuItem;
		OpenProcessMenuItem: TMenuItem;
		Separator1: TMenuItem;
		Separator2: TMenuItem;
		Splitter6: TSplitter;
		Splitter7: TSplitter;
		TSProcesses: TTabSheet;
		tvProcesses: TTreeView;
		lbRunningInstances: TListBox;
		lbFrames: TListBox;
		lbStack: TListBox;
		Log: TMemo;
		MainMenu: TMainMenu;
		MIDetach: TMenuItem;
		MIAttach: TMenuItem;
		MIFile: TMenuItem;
		pcInstances: TPageControl;
		pnFrameVars: TPanel;
		pnInstances: TPanel;
		sgGlobals: TStringGrid;
		PageControl1: TPageControl;
		sgRegisters: TStringGrid;
		sgEventParams: TStringGrid;
		sgLocals: TStringGrid;
		sgFunctions: TStringGrid;
		sgParameters: TStringGrid;
		sgNatives: TStringGrid;
		Splitter1: TSplitter;
		Splitter2: TSplitter;
		Splitter3: TSplitter;
		Splitter4: TSplitter;
		seBytecode: TSynEdit;
		Splitter5: TSplitter;
		tsHandles: TTabSheet;
		tsEventParams: TTabSheet;
		tsCode: TTabSheet;
		tsGlobals: TTabSheet;
		tsRegisters: TTabSheet;
		tsFrames: TTabSheet;
		TSInstances: TTabSheet;
		TSNatives: TTabSheet;
		TSDebug: TTabSheet;
		procedure AboutMenuItemClick(Sender: TObject);
  procedure btnGotoCurrentPositionClick(Sender: TObject);
		procedure ExitMenuItemClick(Sender: TObject);
		procedure FormShow(Sender: TObject);
		procedure FormCreate(Sender: TObject);
		procedure lbFramesSelectionChange(Sender: TObject; User: boolean);
		procedure lbRunningInstancesSelectionChange(Sender: TObject; User: boolean);
		procedure lbStacktraceSelectionChange(Sender: TObject; User: boolean);
		procedure LoadDumpMenuItemClick(Sender: TObject);
		procedure OpenProcessMenuItemClick(Sender: TObject);
		procedure PageControl1Change(Sender: TObject);
		procedure SaveDumpMenuItemClick(Sender: TObject);
		procedure sgFunctionsSelectCell(Sender: TObject; aCol, aRow: Integer;
			var CanSelect: Boolean);
		procedure tvProcessesSelectionChanged(Sender: TObject);
	private
		FJassVM: TJassVM;
		FEventParams: TEventParams;

		FSelectedProcessId: Integer;
		FSelectedProcess: TProcess;
		FSelectedThreadId: Integer;
		FSelectedThread: TThread;
		FSelectedFrameId: Integer;
		FSelectedFrame: TStackFrame;
		FSelectedFunctionId: Integer;
		FSelectedFunction: TFunction;
	private
		procedure AttachToGame(ProcessId: Dword);

		procedure ShowNatives;
		procedure ShowProcesses;
		procedure ShowEventParams;
		procedure ShowVariables;
		procedure ShowRegisters;
		procedure ShowFrames;
		procedure ShowFrameContent;
		procedure ShowFunctions;
		procedure ShowStacktrace;
		procedure ShowFunctionName;
		procedure ShowFunctionCode;

		function FindFunctionByOffset(Offset: SizeUInt): Integer;
		function OffsetToFunctionPointer(Offset: SizeUInt): TFunctionPointer;
		procedure Jump(Offset: SizeUInt);
		procedure GotoCurrentPosition;

		procedure SelectProcess(Index: Integer);
		procedure SelectThread(Index: Integer);
		procedure SelectRunningThread(Index: Integer);
		procedure SelectFrame(Index: Integer);
		procedure SelectFunction(Index: Integer);
	public
		property SelectedProcessId: Integer read FSelectedProcessId write SelectProcess;
		property SelectedProcess: TProcess read FSelectedProcess;
		property SelectedThreadId: Integer read FSelectedThreadId write SelectThread;
		property SelectedThread: TThread read FSelectedThread;
		property SelectedFrameId: Integer read FSelectedFrameId write SelectFrame;
		property SelectedFrame: TStackFrame read FSelectedFrame;
		property SelectedFunctionId: Integer read FSelectedFunctionId write SelectFunction;
		property SelectedFunction: TFunction read FSelectedFunction;
	end;

var
	MainForm: TMainForm;

var
	CheckFirst: TModuleEntry32WArray;

implementation

{$R *.lfm}

function GetTypeName(t: TScriptDataType): String;
const
	TypeNames: array [TScriptDataType] of String =
	(
		'nothing',
		'retaddr',
		'null',
		'code',

		'integer',
		'real',
		'string',
		'handle',
		'boolean',

		'integer[]',
		'real[]',
		'string[]',
		'handle[]',
		'boolean[]'
	);
begin
	if Dword(t) < Length(TypeNames)
		then Result:= TypeNames[t]
		else Result:= 'unknown';
end;

function GetTypeName(id: Dword): String;
begin
	Result:= GetTypeName(TScriptDataType(id));
end;

function GetProcessString(Process: TProcess; hString: Dword): String;
begin
	Result:= Process.Strings.GetDefault(hString, '<string index out of bounds>');
end;

function GetScriptString(Script: TScript; hString: Dword): String;
begin
	Result:= Script.Strings.GetDefault(hString, '<string index out of bounds>');
end;

function GetScriptString(hString: Dword): String;
begin
	Result:= MainForm.SelectedProcess.Script.Strings.GetDefault(
		hString,
		'<string index out of bounds>'
	);
end;

function ValueToString(Strings: TStringsArray; Value: Dword; ValueType: TScriptDataType): String;
begin
	case ValueType of
		stVoid: Result:= 'undefined';
		stNull: Result:= 'null';
		stString: Result:= '"' + Strings.GetDefault(Value, '<string index out of bounds>') + '"';
		stReal: Result:= FloatToStr(PSingle(@Value)^);
		stBoolean: Result:= BoolToStr(PLongBool(@Value)^, True);
		stInteger:  Result:= IntToStr(PInteger(@Value)^);
		else Result:= IntToHex(Value, 8);
	end;
end;

function ScriptValueToString(Value: Dword; ValueType: Byte): String;
begin
	Result:= ValueToString(MainForm.SelectedProcess.Script.Strings, Value, TScriptDataType(ValueType));
end;

function VariableToString(Strings: TStringsArray; const Variable: TMyScriptData): String;
begin
	Result:= ValueToString(Strings, Variable.Value, Variable.DataType);
end;

function OpToStr(const Operation: TInstruction): String;
begin
	case TOperationCode(Operation.id) of
		opEndProgram:   Result:= 'endprogram';
		opFunction:     Result:= Format('function %s: %s', [GetScriptString(Operation.parameter), GetTypeName(Operation.r1)]);
		opEndFunction:  Result:= 'endfunction';
		opLocal:        Result:= Format('local %s %s', [GetTypeName(Operation.r1), GetScriptString(Operation.parameter)]);
		opGlobal:       Result:= Format('global %s %s', [GetTypeName(Operation.r1), GetScriptString(Operation.parameter)]);
		opConstant:     Result:= Format('constant %s %s', [GetTypeName(Operation.r1), GetScriptString(Operation.parameter)]);
		opArgument:     Result:= Format('argument[%d] %s %s', [Operation.r2, GetTypeName(Operation.r1), GetScriptString(Operation.parameter)]);
		opParentType:   Result:= Format('parent %s', [GetScriptString(Operation.parameter)]);
		opChildType:    Result:= Format('child %s', [GetScriptString(Operation.parameter)]);
		opCleanStack:   Result:= Format('cleanstack %d', [Operation.r1]);
		opLiteral:      Result:= Format('<r%d> = %s', [Operation.r1, ScriptValueToString(Operation.parameter, Operation.r2)]);
		opMove:         Result:= Format('<r%d> = <r%d>', [Operation.r1, Operation.r2]);
		opGetVar:       Result:= Format('<r%d> = (%s)%s', [Operation.r1, GetTypeName(Operation.r2), GetScriptString(Operation.parameter)]);
		opGetCode:      Result:= Format('<r%d> = (%s)%s', [Operation.r1, GetTypeName(Operation.r2), GetScriptString(Operation.parameter)]);
		opGetArray:     Result:= Format('<r%d> = (%s)%s[<r%d>]', [Operation.r1, GetTypeName(Operation.r3), GetScriptString(Operation.parameter), Operation.r2]);
		opSetVar:       Result:= Format('%s = <r%d>', [GetScriptString(Operation.parameter), Operation.r1]);
		opSetArray:     Result:= Format('%s[<r%d>] = <r%d>', [GetScriptString(Operation.parameter), Operation.r1, Operation.r2]);
		opPush:         Result:= Format('push <r%d>', [Operation.r1]);
		opPop:          Result:= Format('pop <r%d>', [Operation.r1]);
		opNativeCall:   Result:= Format('ncall %s', [GetScriptString(Operation.parameter)]);
		opCall:         Result:= Format('call %s', [GetScriptString(Operation.parameter)]);
		opI2R:          Result:= Format('i2r <r%d>', [Operation.r1]);
		opAnd:          Result:= Format('<r%d> = <r%d> %s <r%d>', [Operation.r1, Operation.r2, '&&', Operation.r3]);
		opOr:           Result:= Format('<r%d> = <r%d> %s <r%d>', [Operation.r1, Operation.r2, '||', Operation.r3]);
		opEqual:        Result:= Format('<r%d> = <r%d> %s <r%d>', [Operation.r1, Operation.r2, '==', Operation.r3]);
		opNotEqual:     Result:= Format('<r%d> = <r%d> %s <r%d>', [Operation.r1, Operation.r2, '!=', Operation.r3]);
		opLesserEqual:  Result:= Format('<r%d> = <r%d> %s <r%d>', [Operation.r1, Operation.r2, '<=', Operation.r3]);
		opGreaterEqual: Result:= Format('<r%d> = <r%d> %s <r%d>', [Operation.r1, Operation.r2, '>=', Operation.r3]);
		opLesser:       Result:= Format('<r%d> = <r%d> %s <r%d>', [Operation.r1, Operation.r2, '<', Operation.r3]);
		opGreater:      Result:= Format('<r%d> = <r%d> %s <r%d>', [Operation.r1, Operation.r2, '>', Operation.r3]);
		opAdd:          Result:= Format('<r%d> = <r%d> %s <r%d>', [Operation.r1, Operation.r2, '+', Operation.r3]);
		opSub:          Result:= Format('<r%d> = <r%d> %s <r%d>', [Operation.r1, Operation.r2, '-', Operation.r3]);
		opMul:          Result:= Format('<r%d> = <r%d> %s <r%d>', [Operation.r1, Operation.r2, '*', Operation.r3]);
		opDiv:          Result:= Format('<r%d> = <r%d> %s <r%d>', [Operation.r1, Operation.r2, '/', Operation.r3]);
		opModulo:       Result:= Format('<r%d> = <r%d> %s <r%d>', [Operation.r1, Operation.r2, '%', Operation.r3]);
		opNegate:       Result:= Format('negate <r%d>', [Operation.r1]);
		opNot:          Result:= Format('not <r%d>', [Operation.r1]);
		opReturn:       Result:= 'return';
		opLabel:        Result:= Format('label %.8X:', [Operation.parameter]);
		opJumpIfTrue:   Result:= Format('if <r%d> then jmp %.8X', [Operation.r1, Operation.parameter]);
		opJumpIfFalse:  Result:= Format('if !<r%d> then jmp %.8X', [Operation.r1, Operation.parameter]);
		opJump:         Result:= Format('jmp %.8X', [Operation.parameter]);
		else Result:= 'unknown';
	end;
end;

function GetTextWidth(Text: String; Font: TFont): Integer;
var
	Bitmap: TBitmap;
begin
	Bitmap:= TBitmap.Create;

	try
		Bitmap.Canvas.Font:= Font;

		Result:= Bitmap.Canvas.TextWidth(Text);
	finally
		Bitmap.Destroy;
	end;
end;

function GetMaxDecimalDigitWidth(Font: TFont): Integer;
var
	Bitmap: TBitmap;
	i: Integer;
	Width: Integer;
begin
	Bitmap:= TBitmap.Create;

	try
		Bitmap.Canvas.Font:= Font;
		Result:= 0;

		for i:= 0 to 9 do begin
			Width:= Bitmap.Canvas.TextWidth(IntToStr(i));

			if Width > Result then
				Result:= Width;
		end;

	finally
		Bitmap.Destroy;
	end;
end;

procedure AutoSizeNumberedCol(Grid: TStringGrid);
var
	MaxNumberLength: Integer;
	MaxNumberWidth{, ExtraWidth, Padding}: Integer;
begin
	if not (goFixedRowNumbering in Grid.Options) then exit;
	if Grid.FixedCols = 0 then exit;

	MaxNumberLength:= Length( IntToStr(Grid.RowCount) );
	MaxNumberWidth:= MaxNumberLength * GetMaxDecimalDigitWidth(MainForm.Font);
	//ExtraWidth:= GetTextWidth(' ', MainForm.Font) * 2;
	//Padding:= varCellpadding * 2;
	Grid.ColWidths[0]:= MaxNumberWidth {+ ExtraWidth + Padding};
end;

procedure AutoSizeGridColumns(Grid: TStringGrid);
var
	i: Integer;
	ExtraWidth: Integer;
begin
	Grid.AutoSizeColumns();
	AutoSizeNumberedCol(Grid);

	ExtraWidth:= GetTextWidth(' ', Grid.Font) * 2;

	for i:= 0 to Grid.ColCount - 1 do begin
		Grid.ColWidths[i]:= Grid.ColWidths[i] + ExtraWidth;
	end;
end;

function EnableDebugPrivileges: Boolean;
var
	PrivilegeID: LUID;
	Token: Handle;
	Privileges: TTokenPrivileges;
begin
	Result:= False;

	if not LookupPrivilegeValue(nil, SE_DEBUG_NAME, {%H-}PrivilegeID) then exit;

	if not OpenProcessToken(
			GetCurrentProcess(),
			TOKEN_QUERY or TOKEN_ADJUST_PRIVILEGES,
			{%H-}Token
		)
		then exit;

	with Privileges do begin
		PrivilegeCount:= 1;

		with Privileges[0] do begin
			Luid:= PrivilegeID;
			Attributes:= SE_PRIVILEGE_ENABLED;
		end;
	end;

	if not AdjustTokenPrivileges(
			Token,
			False,
			@Privileges,
			SizeOf(Privileges),
			nil,
			nil
		)
		then exit;

	if GetLastError() <> ERROR_SUCCESS then exit;

	CloseHandle(Token);

	Result:= True;
end;

{ TMainForm }

procedure TMainForm.FormCreate(Sender: TObject);
begin
	if EnableDebugPrivileges
		then MainForm.Caption:= MainForm.Caption + ' (*)';
end;

procedure TMainForm.btnGotoCurrentPositionClick(Sender: TObject);
begin
	GotoCurrentPosition;
end;

procedure TMainForm.AboutMenuItemClick(Sender: TObject);
begin
	ShowMessage('Build date: 11.09.2024'#13#10 +
		'Author: IceFog (https://xgm.guru/u/IceFog)'#13#10 +
		'Home page: https//xgm.guru/p/wc3/jass-view'
	);
end;

procedure TMainForm.ExitMenuItemClick(Sender: TObject);
begin
    Close();
end;

procedure TMainForm.FormShow(Sender: TObject);
begin

end;

procedure TMainForm.lbFramesSelectionChange(Sender: TObject; User: boolean);
begin
	SelectedFrameId:= lbFrames.ItemIndex;
end;

procedure TMainForm.lbRunningInstancesSelectionChange(Sender: TObject; User: boolean);
begin
	SelectRunningThread(lbRunningInstances.ItemIndex);
end;

procedure TMainForm.lbStacktraceSelectionChange(Sender: TObject; User: boolean);
begin
	if (lbStacktrace.ItemIndex <> -1) then
		Jump(SizeUInt(lbStacktrace.Items.Objects[lbStacktrace.ItemIndex]))
	else
		SelectedFunctionId:= -1;
end;

procedure TMainForm.LoadDumpMenuItemClick(Sender: TObject);
var
	NewJassVM: TJassVM;
begin
	if OpenDialog.Execute() then begin
		NewJassVM:= TJassVM.Create();
		try
			LoadJassVM(OpenDialog.FileName, NewJassVM);
		except
			NewJassVM.Destroy();
		end;

		FreeAndNil(FJassVM);
		FJassVM:= NewJassVM;
		close_game_process();
		ShowNatives();
		ShowProcesses();
		ShowEventParams();
		SelectedProcessId:= -1;
		SaveDumpMenuItem.Enabled:= True;
	end;
end;

procedure TMainForm.OpenProcessMenuItemClick(Sender: TObject);
begin
	if SelectProcessDialog.ShowModal() = mrOk then begin
		with SelectProcessDialog.ProcessesListBox do begin
			if ItemIndex <> -1
				then AttachToGame(Dword(Items.Objects[ItemIndex]));
		end;
	end;
end;

procedure TMainForm.PageControl1Change(Sender: TObject);
begin

end;

procedure TMainForm.SaveDumpMenuItemClick(Sender: TObject);
begin
	if SaveDialog.Execute() then begin
		SaveJassVM(SaveDialog.FileName, FJassVM);
	end;
end;

procedure TMainForm.sgFunctionsSelectCell(Sender: TObject; aCol, aRow: Integer; var CanSelect: Boolean);
begin
	SelectedFunctionId:= Integer(sgFunctions.Objects[0, aRow]);
end;

procedure TMainForm.tvProcessesSelectionChanged(Sender: TObject);
begin
	if tvProcesses.Selected = nil then begin
		SelectedProcessId:= -1;
		exit;
	end;

	if tvProcesses.Selected.Parent <> nil then begin
		SelectedProcessId:= tvProcesses.Selected.Parent.Index;
		SelectedThreadId:= tvProcesses.Selected.Index;
	end
	else begin
		SelectedProcessId:= tvProcesses.Selected.Index;
	end;
end;

procedure TMainForm.AttachToGame(ProcessId: Dword);
begin
	open_game_process(ProcessId);
	FJassVM:= GetJassVM();
	ShowNatives();
	ShowProcesses();
	ShowEventParams();
	SelectedProcessId:= -1;
	SaveDumpMenuItem.Enabled:= True;
end;

function InRegion(Value, Start: Pointer; Size: SizeUInt): Boolean;
begin
	Result:= (Value >= Start) and (Value < (Start + Size));
end;

function AddrToStr(ProcessId: Dword; Address: Pointer): String;
var
	Module: TModuleEntry32W;
begin
	if ProcessId <> Dword(-1) then begin
		for Module in Modules(ProcessId) do begin
			if InRegion(Address, Module.modBaseAddr, Module.modBaseSize) then begin
				Result:= Format('%s + $%X', [Module.szModule, Address - Module.modBaseAddr]);
				exit;
			end;
		end;
	end;

	Result:= Format('$%P', [Address]);
end;

function GetProcessIdBugless(Process: Handle): Dword;
begin
	if Process <> INVALID_HANDLE_VALUE
		then Result:= GetProcessId(Process)
		else Result:= Dword(-1);
end;

function AddrToStrEx(Process: Handle; Address: Pointer; CheckFirst: TModuleEntry32WArray): String;
var
	Module: TModuleEntry32W;
begin
	for Module in CheckFirst do begin
		if InRegion(Address, Module.modBaseAddr, Module.modBaseSize) then begin
			Result:= Format('%s + $%X', [Module.szModule, Address - Module.modBaseAddr]);
			exit;
		end;
	end;

	Result:= AddrToStr(GetProcessIdBugless(Process), Address);
end;

procedure TMainForm.ShowNatives;
var
	i: Integer;
	Native: TNativeFunction;
begin
	sgNatives.RowCount:= 1 + FJassVM.Natives.Count;

	sgNatives.BeginUpdate;
	for i:= 0 to FJassVM.Natives.Count - 1 do begin
		Native:= FJassVM.Natives.Data[i];

		with sgNatives do begin
			Cells[1, i+1]:= Native.Name;
			Cells[2, i+1]:= Native.Signature;
			Cells[3, i+1]:= AddrToStrEx(WarProcess, Native.Address, CheckFirst);
			//Cells[3, i+1]:= AddrToStr(WarProcId, Native.Address);
		end;
	end;
	AutoSizeGridColumns(sgNatives);
	sgNatives.EndUpdate;
end;

procedure TMainForm.ShowProcesses;
var
	i: Integer;
	Thread: TThread;
	ProcessNode: TTreeNode;
begin
	tvProcesses.Items.Clear;

	tvProcesses.BeginUpdate;
	for i:= 0 to FJassVM.Processes.Count - 1 do begin
		ProcessNode:= tvProcesses.Items.Add(nil, Format('Process %d', [i + 1]));

		for Thread in FJassVM.Processes[i].Threads do begin
			tvProcesses.Items.AddChild(ProcessNode, Format('Thread %d', [Thread.Handle]));
		end;
	end;
	tvProcesses.EndUpdate;

	for Thread in FJassVM.RunningThreads do begin
		lbRunningInstances.Items.Add('Thread %d', [Thread.Handle]);
	end;
end;

procedure TMainForm.ShowEventParams;
var
	MaxLength: Dword = 0;
	EventParamId: TEventParam;
	i: Integer;
begin
	for EventParamId in TEventParam do begin
		MaxLength:= Max(MaxLength, FEventParams[EventParamId].Count);
	end;

	sgEventParams.ColCount:= 1 + MaxLength;
	sgEventParams.RowCount:= 15;

	sgEventParams.BeginUpdate;
	for EventParamId in TEventParam do begin
		sgEventParams.Cells[0, Integer(EventParamId)]:= EventParamReadableName[EventParamId];

		for i:= 0 to FEventParams[EventParamId].Count - 1 do begin
			sgEventParams.Cells[i + 1, Integer(EventParamId)]:= IntToHex(FEventParams[EventParamId][i], 8);
		end;
	end;
	AutoSizeGridColumns(sgEventParams);
	sgEventParams.EndUpdate;
end;

procedure FillGridWithVariables(Grid: TStringGrid; Variables: TVariables);
var
	i: Integer;
begin
	Grid.RowCount:= 1 + Variables.Count;

	Grid.BeginUpdate;
	for i:= 0 to Variables.Count - 1 do begin
		Grid.Cells[1, i+1]:= Variables.Keys[i];
		Grid.Cells[2, i+1]:= GetTypeName(Variables.Data[i].DataType);
		Grid.Cells[3, i+1]:= VariableToString(MainForm.SelectedProcess.Strings, Variables.Data[i]);
	end;
	AutoSizeGridColumns(Grid);
	Grid.EndUpdate;
end;

procedure TMainForm.ShowVariables;
begin
	if SelectedProcess = nil then begin
		sgGlobals.RowCount:= 1;
		exit;
	end;

	FillGridWithVariables(sgGlobals, SelectedProcess.Globals);
end;

procedure TMainForm.ShowRegisters;
var
	i: Integer;
begin
	sgRegisters.RowCount:= 1;

	if SelectedThread = nil then exit;

	sgRegisters.RowCount:= 1 + SelectedThread.Registers.Count;

	sgRegisters.BeginUpdate;
	for i:= 0 to SelectedThread.Registers.Count - 1 do begin
		with SelectedThread.Registers[i] do begin
			sgRegisters.Cells[1, i+1]:= GetTypeName(DataType);
			sgRegisters.Cells[2, i+1]:= ValueToString(SelectedProcess.Strings, Value, DataType);
		end;
	end;
	AutoSizeGridColumns(sgRegisters);
	sgRegisters.EndUpdate;
end;

procedure TMainForm.ShowFrames;
var
	i: Integer;
begin
	lbFrames.Clear;

	if SelectedThread = nil then exit;

	for i:= 0 to SelectedThread.Frames.Count - 1 do begin
		lbFrames.Items.Add('Frame %d', [i + 1]);
	end;
end;

procedure TMainForm.ShowFrameContent;
var
	Data: TMyScriptData;
begin
	lbStack.Clear;
	sgParameters.RowCount:= 1;
	sgLocals.RowCount:= 1;

	if SelectedFrame <> nil then begin
		FillGridWithVariables(sgParameters, SelectedFrame.Arguments);
		FillGridWithVariables(sgLocals, SelectedFrame.Locals);

		for Data in SelectedFrame.Stack do begin
			lbStack.Items.Add(VariableToString(SelectedProcess.Strings, Data));
		end;
	end;
end;

procedure TMainForm.ShowFunctions;
var
	i: Integer;
begin
	sgFunctions.RowCount:= 1;

	if SelectedProcess = nil then exit;

	sgFunctions.RowCount:= 1 + SelectedProcess.Functions.Count;

	sgFunctions.BeginUpdate;
	for i:= 0 to SelectedProcess.Functions.Count - 1 do begin
		with SelectedProcess.Functions[i] do begin
			sgFunctions.Cells[1, i+1]:= Name;
			sgFunctions.Cells[2, i+1]:= GetTypeName(RetType);
			sgFunctions.Cells[3, i+1]:= IntToHex(Offset, 8);
			sgFunctions.Cells[4, i+1]:= IntToHex(Size, 8);

			sgFunctions.Objects[0, i+1]:= TObject(i);
		end;
	end;
	AutoSizeGridColumns(sgFunctions);
	sgFunctions.EndUpdate;
end;

procedure StacktraceAddItem(Offset: SizeUInt);
var
	FunctionPointer: TFunctionPointer;
	FunctionName, ItemName: String;
begin
	with MainForm do begin
		try
			FunctionPointer:= OffsetToFunctionPointer(Offset);
		except
			lbStacktrace.AddItem(Format('Error: Invalid code offset: [%X].', [Offset]), TObject(Offset));
			exit;
		end;

		with FunctionPointer do begin
			FunctionName:= SelectedProcess.Functions[FunctionIndex].Name;

			if InstructionIndex > 0 then
				ItemName:= Format('%s+%d', [FunctionName, InstructionIndex])
			else
				ItemName:= FunctionName;
		end;

		ItemName:= Format('%d. %s', [lbStacktrace.Count + 1, ItemName]);

		lbStacktrace.AddItem(ItemName, TObject(Offset));
	end;
end;

procedure StacktraceAddItemWithFix(Offset: SizeUInt);
begin
	StacktraceAddItem(Offset - SizeOf(TInstruction));
end;

procedure TMainForm.ShowStacktrace;
var
	i: Integer;
begin
	lbStacktrace.Clear;
	if SelectedThread = nil then exit;

	for i:= 0 to SelectedThread.Frames.Count - 2 do begin
		StacktraceAddItemWithFix(SelectedThread.Frames[i].Stack[-1].Value * SizeOf(Dword));
	end;

	StacktraceAddItemWithFix(SelectedThread.Offset);
end;

procedure TMainForm.ShowFunctionName;
begin
	if SelectedFunction <> nil then
		gbCode.Caption:= SelectedFunction.Name
	else
		gbCode.Caption:= '';
end;

procedure TMainForm.ShowFunctionCode;
var
	Instructions: TInstructions;
	Index: Integer;
	s: String;
begin
	seBytecode.Clear;
	if SelectedFunction = nil then exit;

	Instructions:= SelectedProcess.Script.Instructions;
	Index:= SelectedFunction.Offset div SizeOf(TInstruction);

	seBytecode.BeginUpdate;

	while Index < Instructions.Count do begin
		if TOperationCode(Instructions[Index].id) = opEndFunction then break;

		if TOperationCode(Instructions[Index].id) <> opLabel then
			s:= #9 + OpToStr(Instructions[Index])
		else
			s:= OpToStr(Instructions[Index]);

		seBytecode.Lines.Add(s);

		Inc(Index);
	end;

	seBytecode.EndUpdate;
end;

function TMainForm.FindFunctionByOffset(Offset: SizeUInt): Integer;
var
	Low, High, Current: Integer;
	Difference: SizeInt;
	f: TFunction;
begin
	Result:= -1;

	if SelectedProcess = nil then exit;
	if (Offset div SizeOf(TInstruction)) >= SizeUInt(SelectedProcess.Script.Instructions.Count) then exit;
	if SelectedProcess.Functions.Count = 0 then exit;

	Low:= 0;
	High:= SelectedProcess.Functions.Count - 1;

	while (Low <= High) do begin
		Current:= Low + ((High - Low) div 2);
		Difference:= SelectedProcess.Functions[Current].Offset - Offset;

		if Difference > 0 then begin
			High:= Current - 1;
		end
		else if Difference < 0 then begin
			Low:= Current + 1;
			Result:= Current;
		end
		else begin
			Result:= Current;
			break;
		end;
	end;

	if Result <> -1 then begin
		f:= SelectedProcess.Functions[Result];
		if Offset >= (f.Offset + f.Size) then
			Result:= -1;
	end;
end;

function TMainForm.OffsetToFunctionPointer(Offset: SizeUInt): TFunctionPointer;
var
	FunctionIndex: Integer;
	Func: TFunction;
	InstructionIndex: Integer;
begin
	FunctionIndex:= FindFunctionByOffset(Offset);
	if FunctionIndex = -1 then
		raise Exception.CreateFmt('Can''t find function by offset: %d', [Offset]);

	Func:= SelectedProcess.Functions[FunctionIndex];
	InstructionIndex:= (Offset - Func.Offset) div SizeOf(TInstruction);

	Result.FunctionIndex:= FunctionIndex;
	Result.InstructionIndex:= InstructionIndex;
end;

procedure TMainForm.Jump(Offset: SizeUInt);
var
	LineNumber: Integer;
	FunctionPointer: TFunctionPointer;
begin
	SelectedFunctionId:= -1;

	try
		FunctionPointer:= OffsetToFunctionPointer(Offset);
	except
		exit;
	end;

	SelectedFunctionId:= FunctionPointer.FunctionIndex;
	LineNumber:= FunctionPointer.InstructionIndex;

	if LineNumber > seBytecode.Lines.Count - 1 then
		seBytecode.Lines[seBytecode.Lines.Count - 1]:= seBytecode.Lines[seBytecode.Lines.Count - 1] + ' // Current position is outside the function bounds.'
	else
		seBytecode.Lines[LineNumber]:= seBytecode.Lines[LineNumber] + ' // <-----------';
end;

procedure TMainForm.GotoCurrentPosition;
begin
  if (SelectedFrameId > 0) and (SelectedFrame.Stack.Count > 0) then begin
		Jump(SelectedFrame.Stack[-1].Value * 4);
	end
	else if (SelectedThread <> nil) then begin
		Jump(SelectedThread.Offset);
	end;
end;

procedure TMainForm.SelectProcess(Index: Integer);
begin
	if SelectedProcessId = Index then exit;

	if not InRange(Index, 0, FJassVM.Processes.Count - 1) then
		Index:= -1;

	FSelectedProcessId:= Index;

	if SelectedProcessId <> -1 then
		FSelectedProcess:= FJassVM.Processes[SelectedProcessId]
	else
		FSelectedProcess:= nil;

	ShowVariables;
	ShowFunctions;

	SelectThread(-1);
	SelectFunction(-1);
end;

procedure TMainForm.SelectThread(Index: Integer);
begin
	if SelectedThreadId = Index then exit;

	if (SelectedProcess = nil) or not InRange(Index, 0, SelectedProcess.Threads.Count - 1) then
		Index:= -1;

	FSelectedThreadId:= Index;

	if SelectedThreadId <> -1 then
		FSelectedThread:= SelectedProcess.Threads[SelectedThreadId]
	else
		FSelectedThread:= nil;

	ShowRegisters();
	ShowFrames();
	ShowStacktrace();
	SelectedFrameId:= -1;
end;

procedure TMainForm.SelectRunningThread(Index: Integer);
var
	Thread: TThread;
begin
	if not InRange(Index, 0, FJassVM.RunningThreads.Count - 1) then begin
		exit;
	end;

	Thread:= FJassVM.RunningThreads[Index];
	SelectedProcessId:= FJassVM.Processes.IndexOf(Thread.Owner);
	SelectedThreadId:= Thread.Owner.Threads.IndexOf(Thread);
end;

procedure TMainForm.SelectFrame(Index: Integer);
begin
	if SelectedFrameId = Index then exit;

	if (SelectedThread = nil) or not InRange(Index, 0, SelectedThread.Frames.Count - 1) then
		Index:= -1;

	FSelectedFrameId:= Index;

	if SelectedFrameId <> -1 then
		FSelectedFrame:= SelectedThread.Frames[SelectedFrameId]
	else
		FSelectedFrame:= nil;

	ShowFrameContent;
end;

procedure TMainForm.SelectFunction(Index: Integer);
begin
	if SelectedFunctionId = Index then exit;

	if (SelectedProcess = nil) or not InRange(Index, 0, SelectedProcess.Functions.Count - 1) then
		Index:= -1;

	FSelectedFunctionId:= Index;

	if SelectedFunctionId <> -1 then
		FSelectedFunction:= SelectedProcess.Functions[SelectedFunctionId]
	else
		FSelectedFunction:= nil;

	ShowFunctionName;
	ShowFunctionCode;
end;

end.

































