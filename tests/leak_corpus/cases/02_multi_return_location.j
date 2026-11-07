function MultiReturn takes boolean flag, unit u returns nothing
    local location loc = GetUnitLoc(u)
    if flag then
        call SetUnitPositionLoc(u, loc)
        return
    endif
    call SetUnitPositionLoc(u, loc)
    return
endfunction
