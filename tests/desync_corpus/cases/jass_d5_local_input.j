function Trig_D5 takes nothing returns nothing
    if GetCameraTargetPositionX() > 0.0 then
        call BJDebugMsg("camera")
    endif
endfunction

function Trig_D5_Mixed takes nothing returns nothing
    if GetLocalPlayer() == Player(0) and GetSelectedUnit() != null then
        call BJDebugMsg("selected")
    endif
endfunction
