program JassView;

{$mode objfpc}{$H+}

uses
	{$IFDEF UNIX}{$IFDEF UseCThreads}
	cthreads,
	{$ENDIF}{$ENDIF}
	Interfaces, // this includes the LCL widgetset
	Forms, MainUnit, jassvm, wc3remote, SelectProcessDialogUnit, JassVMSerialization, Controls
	{ you can add units after this };

{$R *.res}

begin
	RequireDerivedFormResource:=True;
	Application.Scaled:=True;
	Application.Initialize;
	Application.CreateForm(TMainForm, MainForm);
	Application.CreateForm(TSelectProcessDialog, SelectProcessDialog);
	Application.Run;
end.

