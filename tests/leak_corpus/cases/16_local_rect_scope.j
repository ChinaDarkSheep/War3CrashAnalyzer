function LocalRect takes nothing returns nothing
    local rect r = Rect(0.0, 0.0, 100.0, 100.0)
    call RegionAddRect(CreateRegion(), r)
endfunction
