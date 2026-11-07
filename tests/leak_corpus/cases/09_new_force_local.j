function NewForceLocal takes player p returns nothing
    local force f = CreateForce()
    call ForceAddPlayer(f, p)
    call ForceRemovePlayer(f, p)
endfunction
