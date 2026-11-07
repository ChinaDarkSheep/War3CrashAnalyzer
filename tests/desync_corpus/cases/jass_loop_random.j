function Trig_Loop takes nothing returns nothing
    local integer i = 0
    loop
        exitwhen i >= 3
        if GetLocalPlayer() == Player(0) then
            set udg_TempInt = GetRandomInt(1, 6)
        endif
        set i = i + 1
    endloop
endfunction
