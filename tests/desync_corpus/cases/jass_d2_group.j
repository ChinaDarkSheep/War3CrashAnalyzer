function Trig_D2_Enum takes nothing returns nothing
    call SetUnitVertexColor(GetEnumUnit(), 255, 0, 0, 255)
endfunction

function Trig_D2 takes nothing returns nothing
    if GetLocalPlayer() == Player(0) then
        call ForGroup(udg_TempGroup, function Trig_D2_Enum)
    endif
endfunction
