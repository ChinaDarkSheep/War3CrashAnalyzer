function Trig_D1 takes nothing returns nothing
    if GetLocalPlayer() == Player(0) then
        call CreateUnit(Player(0), 'hfoo', 0.0, 0.0, 0.0)
    endif
endfunction
