function Tick takes nothing returns nothing
endfunction

function LongTimer takes nothing returns nothing
    local timer t = CreateTimer()
    call TimerStart(t, 1.0, true, function Tick)
endfunction
