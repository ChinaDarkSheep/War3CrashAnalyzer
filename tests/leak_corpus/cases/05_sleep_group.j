function Sleepy takes unit u returns nothing
    local group g = CreateGroup()
    call TriggerSleepAction(2.0)
    call GroupAddUnit(g, u)
    call ForGroup(g, function DoNothing)
endfunction
