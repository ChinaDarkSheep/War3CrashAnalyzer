unit SelectProcessDialogUnit;

{$mode ObjFPC}{$H+}

interface

uses
	JwaWindows,
	Classes, SysUtils, Forms, Controls, Graphics, Dialogs, StdCtrls, ExtCtrls,
	ProcessUtils;

type

	{ TSelectProcessDialog }

	TSelectProcessDialog = class(TForm)
		ButtonCancel: TButton;
		ButtonSelect: TButton;
		ButtonsPanel: TPanel;
		ProcessesListBox: TListBox;
		procedure FormShow(Sender: TObject);
	private

	public

	end;

var
	SelectProcessDialog: TSelectProcessDialog;

implementation

{$R *.lfm}

{ TSelectProcessDialog }

procedure TSelectProcessDialog.FormShow(Sender: TObject);
var
	ProcessEntry: TProcessEntry32W;
begin
	ProcessesListBox.Clear();

	for ProcessEntry in Processes() do begin
		with ProcessEntry do begin
			ProcessesListBox.Items.AddObject(
				'%d %s', [
					th32ProcessID,
					szExeFile
				],
				TObject(th32ProcessID)
			);
		end;
	end;
end;

end.

