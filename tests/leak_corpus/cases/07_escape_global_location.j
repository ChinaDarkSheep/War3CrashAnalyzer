function EscapeGlobal takes unit u returns nothing
    local location loc = GetUnitLoc(u)
    set udg_savedLoc = loc
endfunction
