local list = {}
for _, value in pairs(list) do
    print(value)
end
local roll = math.random(1, 100)
local now = os.time()
if GetLocalPlayer() == Player(0) then
    print("host")
end
