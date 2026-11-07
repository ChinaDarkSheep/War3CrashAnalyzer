function Trig_D3 takes nothing returns nothing
    local integer roll = 0
    if GetLocalPlayer() == Player(0) then
        set roll = GetRandomInt(1, 100)
        call BJDebugMsg(I2S(roll))
    endif
endfunction
