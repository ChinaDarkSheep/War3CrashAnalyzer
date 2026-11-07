function Trig_D4_Read takes nothing returns nothing
    call BJDebugMsg(I2S(udg_Score))
endfunction

function Trig_D4 takes nothing returns nothing
    if GetLocalPlayer() == Player(0) then
        set udg_Score = 10
    endif
endfunction
