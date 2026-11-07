function Trig_Else takes nothing returns nothing
    if GetLocalPlayer() == Player(0) then
        call BJDebugMsg("host")
    else
        call CreateUnit(Player(1), 'hfoo', 0.0, 0.0, 0.0)
    endif
endfunction
