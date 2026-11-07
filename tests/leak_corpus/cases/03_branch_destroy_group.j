function BranchDestroy takes boolean flag, unit u returns nothing
    local group g = CreateGroup()
    if flag then
        call GroupAddUnit(g, u)
        call DestroyGroup(g)
    else
        call GroupAddUnit(g, u)
        call ForGroup(g, function DoNothing)
    endif
endfunction
