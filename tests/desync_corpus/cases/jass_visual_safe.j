function Trig_Visual takes nothing returns nothing
    if GetLocalPlayer() == Player(0) then
        call SetCameraField(CAMERA_FIELD_TARGET_DISTANCE, 2000.0, 0.0)
        call ClearSelection()
        call BJDebugMsg("only local")
    endif
endfunction
