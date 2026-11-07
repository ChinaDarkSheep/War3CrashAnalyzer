function SharedForceGlobal takes player p returns nothing
    set bj_sharedForce = GetPlayersAll()
    call ForceAddPlayer(bj_sharedForce, p)
endfunction

function SharedForceLocal takes player p returns nothing
    local force f = GetPlayersAll()
    call ForceAddPlayer(f, p)
endfunction
