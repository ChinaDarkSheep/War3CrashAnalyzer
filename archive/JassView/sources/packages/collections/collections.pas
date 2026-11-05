{ This file was automatically created by Lazarus. Do not edit!
  This source is only used to compile and install the package.
 }

unit collections;

{$warn 5023 off : no warning about unused units}
interface

uses
    handletables, pool, ArrayList, handlegenerators, comparators, 
    LazarusPackageIntf;

implementation

procedure Register;
begin
end;

initialization
  RegisterPackage('collections', @Register);
end.
