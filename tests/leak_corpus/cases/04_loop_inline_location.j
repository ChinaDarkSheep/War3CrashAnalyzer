function LoopInline takes integer n, unit u returns nothing
    local integer i = 0
    loop
        exitwhen i >= n
        call SetUnitPositionLoc(u, GetUnitLoc(u))
        set i = i + 1
    endloop
endfunction
