function Idempotent takes unit u returns nothing
    local location loc = GetUnitLoc(u)
    call SetUnitPositionLoc(u, loc)
endfunction
