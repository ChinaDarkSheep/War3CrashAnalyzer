{ This file was automatically created by Lazarus. Do not edit!
  This source is only used to compile and install the package.
 }

unit wc3;

{$warn 5023 off : no warning about unused units}
interface

uses
    wc3collections, wc3jassvm, wc3main, wc3memory, wc3props, wc3refcnt, 
    wc3string, wc3stringhash, wc3game, wc3timer, wc3tls, wc3files, wc3agent, 
    wc3observer, wc3nettag, wc3typeid, wc3player, wc3_chat_command, 
    wc3_native_signature_parser, wc3netdata, wc3netcommands, 
    wc3_observer_callback, wc3gui, wc3float, wc3Debug, wc3_game_state, 
    LazarusPackageIntf;

implementation

procedure Register;
begin
end;

initialization
  RegisterPackage('wc3', @Register);
end.
