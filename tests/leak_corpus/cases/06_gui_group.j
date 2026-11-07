function GuiGroup takes player p returns nothing
    set bj_wantDestroyGroup = true
    call ForGroupBJ(GetUnitsOfPlayerAll(p), function DoNothing)
endfunction
