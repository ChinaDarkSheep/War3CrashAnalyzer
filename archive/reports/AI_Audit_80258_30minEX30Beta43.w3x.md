# JASS 脚本分析报告 (AI 辅助修复专用)

- **目标地图**: 80258_30minEX30Beta43.w3x
- **分析时间**: 2026-11-04 23:50:35
- **发现风险函数**: 193 个

## 建议操作
请将以下代码块提交给 AI (如 ChatGPT/Claude/Trae)，并询问：
> "这些 JASS 函数存在泄露或同步风险吗？请帮我修复它们。"

### 风险函数 #1 (风险评分: 15)
```jass
function Quest_New_Use takes nothing returns nothing
local integer Slot
local boolean QuestStart=false
local integer hi
local item Item
local item BuyItem=GetSoldItem()
local integer itid
local integer select
local real x
local real y
local real x1
local real y1
local integer id=GetPlayerId(GetOwningPlayer(GetBuyingUnit()))
local timer t
local timer t2
local integer h
local integer ht
local integer ht2
local integer gold
local integer a=0
local integer b=0
local integer c=0
local integer d=0
local integer questB=0
local integer ra
local real dmg
local real hp
local real r
local real angle
local real dist
local integer lvl
local integer reward
local unit u
local group g
local integer slot
local real up=1
if HardcoreUP10==2 then
set up=up+0.4
endif
call PauseTimer(TimerResetQuest)
if GetUnitTypeId(GetSellingUnit())=='h043' then
if GetItemTypeId(BuyItem)=='thdm' then
set Item=UnitItemInSlot(BaseGuild,0)
set slot=0
set questB=1
elseif GetItemTypeId(BuyItem)=='srtl' then
set Item=UnitItemInSlot(BaseGuild,1)
set slot=1
set questB=1
elseif GetItemTypeId(BuyItem)=='blba' then
set Item=UnitItemInSlot(BaseGuild,2)
set slot=2
set questB=1
elseif GetItemTypeId(BuyItem)=='tels' then
set Item=UnitItemInSlot(BaseGuild,3)
set slot=3
set questB=1
elseif GetItemTypeId(BuyItem)=='anfg' then
set Item=UnitItemInSlot(BaseGuild,4)
set slot=4
set questB=1
elseif GetItemTypeId(BuyItem)=='soul' then
set Item=UnitItemInSlot(BaseGuild,5)
set slot=5
set questB=1
elseif GetItemTypeId(BuyItem)=='esaz' then
if GetLocalPlayer()==Player(id)then
call ClearTextMessages()
endif
set bj_forLoopAIndex=0
loop
exitwhen bj_forLoopAIndex>5
call DisplayTextToForce(bj_FORCE_PLAYER[id],"|cffffcc00Задание №|r"+I2S(bj_forLoopAIndex+1)+": "+LoadStr(udg_hash,GetHandleId(UnitItemInSlot(BaseGuild,bj_forLoopAIndex)),'t'))
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
call RemoveItem(BuyItem)
endif
if questB==1 then
set QuestStart=true
set hi=GetHandleId(UnitItemInSlot(BaseGuild,slot))
set lvl=LoadInteger(udg_hash,GetHandleId(Item),'l')
set reward=LoadInteger(udg_hash,GetHandleId(Item),'r')
endif
if QuestStart==false then
elseif s__PlayerQuest[id]>0 then
call DisplayTextToForce(bj_FORCE_PLAYER[id],"|cffffcc00В данный момент вы не можете выбрать новое задание|r")
call FlushChildHashtable(udg_hash,GetHandleId(BuyItem))
call RemoveItem(BuyItem)
else
set itid=GetItemTypeId(Item)
if itid=='cnob' or itid=='dsum' or itid=='sbch' then
if s__Quests_Guild_unlock[sQuest[0]]==0 then
call DisplayTextToForce(bj_FORCE_PLAYER[id],"Все точки заняты")
set QuestStart=false
else
set select=GetQuest(0)
set x=s___Quests_Guild_x[s__Quests_Guild_x[sQuest[0]]+select]
set y=s___Quests_Guild_y[s__Quests_Guild_y[sQuest[0]]+select]
set u=CreateUnit(Player(11),'n07H',x,y,0.)
set h=GetHandleId(u)
call UnitAddAbility(u,'A17N')
call SetUnitAbilityLevel(u,'A17N',11)
if itid=='cnob' then
set r=400.
set hp=1500.
set dmg=100.
set gold=225+GetRandomInt(1,4)*25
elseif itid=='dsum' then
set r=1250.
set hp=7000.
set dmg=450.
set gold=500+GetRandomInt(1,6)*25
elseif itid=='sbch' then
set r=4000.
set hp=15000.
set dmg=900.
set gold=1000+GetRandomInt(1,4)*50
endif
set hp=hp*up
set dmg=dmg*up
if HardcoreBuff10==4 then
set gold=R2I(gold*1.3)
endif
call UnitAddAbility(u,'A1DX')
call UnitAddAbility(u,'A007')
call SummonStats(false,R2I(hp),R2I(dmg),u,u)
call SetUnitOwner(u,Player(PLAYER_NEUTRAL_AGGRESSIVE),true)
call UnitRemoveAbility(u,'A007')
call PingMinimapForForceEx(bj_FORCE_PLAYER[id],x,y,60.,bj_MINIMAPPINGSTYLE_FLASHY,20.,20.,80.)
call DisplayTextToForce(bj_FORCE_PLAYER[id],"|cffffcc00Убейте бандита в заданной точке в течении 2 минут!|r")
call DisplayTextToForce(bj_FORCE_PLAYER[id],"|cffffcc00Награда "+I2S(gold)+" ед. золота|r")
set t=CreateTimer()
set ht=GetHandleId(t)
call SaveReal(udg_hash,h,'c',r)
call SaveInteger(udg_hash,h,'l',lvl)
call SaveUnitHandle(udg_hash,ht,0,u)
call SaveInteger(udg_hash,ht,4,id)
call SaveInteger(udg_hash,ht,1,120)
call SaveInteger(udg_hash,ht,2,gold)
call SaveInteger(udg_hash,ht,'r',reward)
call SaveInteger(udg_hash,ht,'l',lvl)
call SaveInteger(udg_hash,ht,'t',1)
set t2=CreateTimer()
call TimerStart(t2,120.,false,function Quest_New_TimerDialog)
set bj_lastCreatedTimerDialog=CreateTimerDialogBJ(t2,"Задание гильдии")
call SaveTimerDialogHandle(udg_hash,ht,10,bj_lastCreatedTimerDialog)
call TimerDialogDisplay(bj_lastCreatedTimerDialog,false)
call TimerDialogDisplayForPlayerBJ(true,bj_lastCreatedTimerDialog,Player(id))
call TimerStart(t,1.,true,function Quest_New_Bandit)
endif
elseif itid=='spsh' or itid=='wolg' or itid=='mgtk' or itid=='dkfw' then
if s__Quests_Guild_unlock[sQuest[1]]==0 then
call DisplayTextToForce(bj_FORCE_PLAYER[id],"|cffffcc00Все точки заняты|r")
set QuestStart=false
else
set select=GetQuest(1)
set x=s___Quests_Guild_x[s__Quests_Guild_x[sQuest[1]]+select]
set y=s___Quests_Guild_y[s__Quests_Guild_y[sQuest[1]]+select]
set a=0
set b=0
set c=0
set d=0
set r=0.
if lvl==1 then
set gold=250+GetRandomInt(1,4)*20
set ra=GetRandomInt(1,4)
if ra==1 then
set hp=250
set dmg=20
set a=4
set b='nmrl'
set c=3
set d='nmrr'
set r=2.
elseif ra==2 then
set hp=200
set dmg=14
set a=8
set b='nkob'
set c=2
set d='nkog'
set r=2.
elseif ra==3 then
set hp=450
set dmg=30
set a=4
set b='nmcf'
set c=1
set d='nmsn'
set r=3.
else
set hp=300
set dmg=20
set a=4
set b='ngna'
set c=4
set d='ngno'
set r=1.25
endif
elseif lvl==2 then
set gold=500+GetRandomInt(1,4)*40
set ra=GetRandomInt(1,4)
if ra==1 then
set hp=1200
set dmg=60
set a=4
set b='nftb'
set c=2
set d='nfsh'
set r=1.5
elseif ra==2 then
set hp=2000
set dmg=125
set a=2
set b='u00L'
set c=2
set d='u00M'
set r=1.
elseif ra==3 then
set hp=4000
set dmg=300
set a=1
set b='nsgt'
set c=1
set d='nssp'
set r=1.
else
set hp=1750
set dmg=120
set a=6
set b='ntka'
endif
elseif lvl==3 then
set gold=850+GetRandomInt(1,5)*50
set ra=GetRandomInt(1,4)
if ra==1 then
set hp=3000
set dmg=200
set a=4
set b='nltc'
set c=2
set d='nlsn'
set r=2.
elseif ra==2 then
set hp=3250
set dmg=300
set a=3
set b='n02B'
set c=3
set d='n05P'
set r=1.
elseif ra==3 then
set hp=5250
set dmg=400
set a=3
set b='nowe'
set c=0
else
set hp=2500
set dmg=225
set a=8
set b='u00T'
set c=0
endif
elseif lvl==4 then
set gold=2000+GetRandomInt(0,5)*75
set ra=GetRandomInt(1,3)
if ra==1 then
set hp=18000
set dmg=750
set a=4
set b='n00F'
set c=0
elseif ra==2 then
set hp=15500
set dmg=550
set a=5
set b='n00W'
else
set hp=22000
set dmg=750
set a=3
set b='u01J'
set c=0
endif
endif
set hp=hp*up
set dmg=dmg*up
if HardcoreBuff10==4 then
set gold=R2I(gold*1.3)
endif
set g=CreateGroup()
call PingMinimapForForceEx(bj_FORCE_PLAYER[id],x,y,60.,bj_MINIMAPPINGSTYLE_FLASHY,20.,20.,80.)
call DisplayTextToForce(bj_FORCE_PLAYER[id],"|cffffcc00Уничтожьте логово и его монстров стражников!|r")
call DisplayTextToForce(bj_FORCE_PLAYER[id],"|cffffcc00Награда "+I2S(gold)+" ед. золота|r")
set u=CreateUnit(Player(11),'nmer',x,y,0.)
call UnitAddAbility(u,'A007')
if lvl==1 then
call SummonStats(false,R2I(750*up)-100,0,u,u)
elseif lvl==2 then
call SummonStats(false,R2I(2500*up)-100,0,u,u)
elseif lvl==3 then
call SummonStats(false,R2I(5500*up)-100,0,u,u)
elseif lvl==4 then
call SummonStats(false,R2I(20000*up)-100,0,u,u)
endif
call SetUnitOwner(u,Player(PLAYER_NEUTRAL_AGGRESSIVE),true)
call UnitRemoveAbility(u,'A007')
call GroupAddUnit(g,u)
if a>0 then
set bj_forLoopAIndex=1
loop
exitwhen bj_forLoopAIndex>a
set x1=x+180*Cos(((360/a)*bj_forLoopAIndex)*bj_DEGTORAD)
set y1=y+180*Sin(((360/a)*bj_forLoopAIndex)*bj_DEGTORAD)
set u=CreateUnit(Player(11),b,x1,y1,0.)
call UnitAddAbility(u,'A007')
call SummonStats(false,R2I(hp),R2I(dmg),u,u)
call SetUnitOwner(u,Player(PLAYER_NEUTRAL_AGGRESSIVE),true)
call UnitRemoveAbility(u,'A007')
call UnitAddAbility(u,'A1DX')
call GroupAddUnit(g,u)
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
endif
if c>0 then
set bj_forLoopAIndex=1
loop
exitwhen bj_forLoopAIndex>c
set x1=x+210*Cos(((360/c)*bj_forLoopAIndex)*bj_DEGTORAD)
set y1=y+210*Sin(((360/c)*bj_forLoopAIndex)*bj_DEGTORAD)
set u=CreateUnit(Player(11),d,x1,y1,0.)
call UnitAddAbility(u,'A007')
call SummonStats(false,R2I(r*hp),R2I(r*dmg),u,u)
call SetUnitOwner(u,Player(PLAYER_NEUTRAL_AGGRESSIVE),true)
call UnitRemoveAbility(u,'A007')
call UnitAddAbility(u,'A1DX')
call GroupAddUnit(g,u)
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
endif
set t=CreateTimer()
set ht=GetHandleId(t)
call SaveInteger(udg_hash,ht,0,id)
call SaveInteger(udg_hash,ht,1,120)
call SaveInteger(udg_hash,ht,2,gold)
call SaveGroupHandle(udg_hash,ht,0,g)
call SaveInteger(udg_hash,ht,'l',lvl)
call SaveInteger(udg_hash,ht,'r',reward)
call SaveInteger(udg_hash,ht,'t',2)
set t2=CreateTimer()
call TimerStart(t2,120.,false,function Quest_New_TimerDialog)
set bj_lastCreatedTimerDialog=CreateTimerDialogBJ(t2,"Задание гильдии")
call SaveTimerDialogHandle(udg_hash,ht,10,bj_lastCreatedTimerDialog)
call TimerDialogDisplay(bj_lastCreatedTimerDialog,false)
call TimerDialogDisplayForPlayerBJ(true,bj_lastCreatedTimerDialog,Player(id))
call TimerStart(t,1.,true,function Quest_New_Lair)
endif
elseif itid=='amrc' or itid=='gobm' or itid=='envl' or itid=='iwbr' then
if s__Quests_Guild_unlock[sQuest[2]]==0 then
call DisplayTextToForce(bj_FORCE_PLAYER[id],"Все точки заняты")
set QuestStart=false
else
set select=GetQuest(2)
set x=s___Quests_Guild_x[s__Quests_Guild_x[sQuest[2]]+select]
set y=s___Quests_Guild_y[s__Quests_Guild_y[sQuest[2]]+select]
if lvl==2 then
set gold=800+GetRandomInt(0,4)*50
if HardcoreBuff10==4 then
set gold=R2I(gold*1.3)
endif
set b=gold+350*udg_PN
set b=(b/udg_PN)
set ra=GetRandomInt(1,3)
if ra==1 then
set hp=9750-2000
set dmg=475-75
set r=30
set a='nbdo'
elseif ra==2 then
set hp=7800-1800
set dmg=350-50
set r=20
set a='nbdk'
else
set hp=8100-2000
set dmg=0
set r=20
set a='nser'
endif
elseif lvl==3 then
set gold=2000+GetRandomInt(0,5)*100
if HardcoreBuff10==4 then
set gold=R2I(gold*1.3)
endif
set b=gold+800*udg_PN
set b=(b/udg_PN)
set ra=GetRandomInt(1,3)
if ra==1 then
set hp=33000-2000
set dmg=2000-75
set r=50
set a='nbdo'
elseif ra==2 then
set hp=25000-1800
set dmg=1400-50
set r=40
set a='nbdk'
else
set hp=27000-2000
set dmg=0
set r=40
set a='nser'
endif
elseif lvl==4 then
set gold=4000+GetRandomInt(0,5)*125
if HardcoreBuff10==4 then
set gold=R2I(gold*1.3)
endif
set b=gold+2100*udg_PN
set b=(b/udg_PN)
set ra=GetRandomInt(1,3)
if ra==1 then
set hp=75000-2000
set dmg=3750-75
set r=75
set a='nbdo'
elseif ra==2 then
set hp=62000-1800
set dmg=4400-50
set r=60
set a='nbdk'
else
set hp=68000-2000
set dmg=0
set r=60
set a='nser'
endif
else
set gold=400+GetRandomInt(0,5)*25
if HardcoreBuff10==4 then
set gold=R2I(gold*1.3)
endif
set b=gold+150*udg_PN
set b=(b/udg_PN)
set ra=GetRandomInt(1,3)
if ra==1 then
set hp=3200-2000
set dmg=150-75
set r=15
set a='nbdo'
elseif ra==2 then
set hp=2250-1800
set dmg=80-50
set r=10
set a='nbdk'
else
set hp=0
set dmg=0
set r=10
set a='nser'
endif
endif
call PingMinimapForForceEx(bj_FORCE_PLAYER[id],x,y,60.,bj_MINIMAPPINGSTYLE_FLASHY,20.,60.,80.)
call DisplayTextToForce(bj_FORCE_PLAYER[id],"|cffffcc00Убейте босса и получите награду!|r")
call DisplayTextToForce(bj_FORCE_PLAYER[id],"|cffffcc00Награда "+I2S(b)+" ед. золота (Усиливается приростом золота)|r")
set bj_forLoopAIndex=0
loop
exitwhen bj_forLoopAIndex>8
if bj_forLoopAIndex !=id then
call PingMinimapForForceEx(bj_FORCE_PLAYER[bj_forLoopAIndex],x,y,15.,bj_MINIMAPPINGSTYLE_FLASHY,20.,20.,80.)
call DisplayTextToForce(bj_FORCE_PLAYER[bj_forLoopAIndex],"|cffffcc00Помогите убить босса игроку"+GetPlayerName(Player(id))+"|r")
call DisplayTextToForce(bj_FORCE_PLAYER[bj_forLoopAIndex],"|cffffcc00Награда "+I2S(b)+" ед. золота (Усиливается приростом золота)|r")
endif
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
set u=CreateUnit(Player(11),a,x,y,0.)
if ra==1 then
call SetUnitScalePercent(u,lvl*20+120,lvl*20+120,lvl*20+120)
else
call SetUnitScalePercent(u,lvl*15+75,lvl*15+75,lvl*15+75)
endif
set hp=hp*up
set dmg=dmg*up
set dmg=dmg*(0.9+0.1*udg_PN)
set hp=hp*(0.75+0.15*udg_PN)
call UnitAddAbility(u,'A0MR')
call UnitAddAbility(u,'A007')
call SummonStats(false,R2I(hp),R2I(dmg),u,u)
call UnitRemoveAbility(u,'A007')
if lvl==4 then
call UnitAddAbility(u,'A0S7')
elseif lvl==2 then
call UnitAddAbility(u,'A12I')
elseif lvl==3 then
call UnitAddAbility(u,'A0S8')
endif
call UnitAddAbility(u,'A05D')
call UnitAddAbility(u,'A1DX')
call UnitAddAbility(u,'A17O')
call SetUnitAbilityLevel(u,'A17O',1+R2I(r)/3)
if GetUnitTypeId(u)=='nbdk' then
if lvl==4 then
set dmg=1600
elseif lvl==3 then
set dmg=800
elseif lvl==2 then
set dmg=400
else
set dmg=200
endif
set dmg=dmg*(0.95+0.05*udg_PN)
set x=GetUnitX(u)
set y=GetUnitY(u)
set dist=100.
set angle=100.
set x1=x+dist*Cos(0.*bj_DEGTORAD)
set y1=y+dist*Sin(0.*bj_DEGTORAD)
set bj_lastCreatedUnit=CreateUnit(GetOwningPlayer(u),'ntor',x1,y1,0.)
set t=CreateTimer()
set ht=GetHandleId(t)
call SaveUnitHandle(udg_hash,ht,0,bj_lastCreatedUnit)
call SaveUnitHandle(udg_hash,ht,1,u)
call SaveReal(udg_hash,ht,0,dist)
call SaveReal(udg_hash,ht,1,0.)
call SaveReal(udg_hash,ht,2,dmg)
call TimerStart(t,0.03,true,function Quest_New_Boss_Tornado)
set x1=x+dist*Cos(180.*bj_DEGTORAD)
set y1=y+dist*Sin(180.*bj_DEGTORAD)
set bj_lastCreatedUnit=CreateUnit(GetOwningPlayer(u),'ntor',x1,y1,0.)
set t=CreateTimer()
set ht=GetHandleId(t)
call SaveUnitHandle(udg_hash,ht,0,bj_lastCreatedUnit)
call SaveUnitHandle(udg_hash,ht,1,u)
call SaveReal(udg_hash,ht,0,dist)
call SaveReal(udg_hash,ht,1,180.)
call SaveReal(udg_hash,ht,2,dmg)
call TimerStart(t,0.03,true,function Quest_New_Boss_Tornado)
endif
call UnitRemoveAbility(u,'A007')
set t=CreateTimer()
set ht=GetHandleId(t)
call SaveInteger(udg_hash,ht,0,id)
call SaveInteger(udg_hash,ht,1,120)
call SaveInteger(udg_hash,ht,2,gold)
call SaveUnitHandle(udg_hash,ht,0,u)
call SaveInteger(udg_hash,ht,'p',b)
call SaveInteger(udg_hash,ht,'l',lvl)
call SaveInteger(udg_hash,ht,'r',reward)
call SaveInteger(udg_hash,ht,'t',3)
set t2=CreateTimer()
call TimerStart(t2,120.,false,function Quest_New_TimerDialog)
set bj_lastCreatedTimerDialog=CreateTimerDialogBJ(t2,"Задание гильдии")
call SaveTimerDialogHandle(udg_hash,ht,10,bj_lastCreatedTimerDialog)
call TimerDialogDisplay(bj_lastCreatedTimerDialog,false)
call TimerDialogDisplayForPlayerBJ(true,bj_lastCreatedTimerDialog,Player(id))
call TimerStart(t,1.,true,function Quest_New_Boss)
endif
elseif itid=='ward' or itid=='penr' or itid=='pmna' then
if s__Quests_Guild_unlock[sQuest[3]]==0 then
call DisplayTextToForce(bj_FORCE_PLAYER[id],"Все точки заняты")
set QuestStart=false
else
set select=GetQuest(3)
set x=s___Quests_Guild_x[s__Quests_Guild_x[sQuest[3]]+select]
set y=s___Quests_Guild_y[s__Quests_Guild_y[sQuest[3]]+select]
if itid=='ward' then
set gold=300+GetRandomInt(0,4)*15
set a=2
set b=120
elseif itid=='penr' then
set gold=750+GetRandomInt(0,6)*25
set a=4
set b=150
elseif itid=='pmna' then
set gold=1250+GetRandomInt(0,10)*25
set a=5
set b=180
endif
if HardcoreBuff10==4 then
set gold=R2I(gold*1.3)
endif
call PingMinimapForForceEx(bj_FORCE_PLAYER[id],x,y,60.,bj_MINIMAPPINGSTYLE_FLASHY,20.,20.,80.)
call DisplayTextToForce(bj_FORCE_PLAYER[id],"|cffffcc00Найдите "+I2S(a)+" шт. целебные травы в указанной зоне в течении 2 минут!|r")
call DisplayTextToForce(bj_FORCE_PLAYER[id],"|cffffcc00Награда "+I2S(gold)+" ед. золота|r")
set t=CreateTimer()
set ht=GetHandleId(t)
call SaveInteger(udg_hash,ht,0,id)
call SaveInteger(udg_hash,ht,1,b*10)
call SaveInteger(udg_hash,ht,2,gold)
call SaveInteger(udg_hash,ht,3,a)
call SaveReal(udg_hash,ht,4,100000)
call SaveInteger(udg_hash,ht,'l',lvl)
call SaveInteger(udg_hash,ht,'r',reward)
call SaveInteger(udg_hash,ht,'t',4)
set t2=CreateTimer()
call TimerStart(t2,b,false,function Quest_New_TimerDialog)
set bj_lastCreatedTimerDialog=CreateTimerDialogBJ(t2,"Задание гильдии")
call SaveTimerDialogHandle(udg_hash,ht,10,bj_lastCreatedTimerDialog)
call TimerDialogDisplay(bj_lastCreatedTimerDialog,false)
call TimerDialogDisplayForPlayerBJ(true,bj_lastCreatedTimerDialog,Player(id))
call TimerStart(t,0.1,true,function Quest_New_FlowerMain)
if(x>250. and x<450.)and(y>14900. and y<15100.)then
set b=1
call GetRandomItemInList(9,a)
elseif(x>3400. and x<3600.)and(y<-400. and y>-600.)then
set b=2
call GetRandomItemInList(9,a)
elseif(x<-4900. and x>-5100.)and(y<-4900. and y>-5100.)then
set b=3
call GetRandomItemInList(9,a)
elseif(x>-10100. and x<-9900.)and(y>6900. and y<7100.)then
set b=4
call GetRandomItemInList(9,a)
elseif(x>-1100. and x<-900.)and(y>5400. and y<5600.)then
set b=5
call GetRandomItemInList(9,a)
elseif(x>1400. and x<1600.)and(y>21900. and y<22100.)then
set b=6
call GetRandomItemInList(9,a)
elseif(x>-12100. and x<-11900.)and(y>1300. and y<1500.)then
set b=7
call GetRandomItemInList(9,a)
elseif(x>-10500. and x<-9500.)and(y>20500. and y<21500.)then
set b=8
call GetRandomItemInList(9,a)
else
set b=1
call GetRandomItemInList(9,a)
endif
set bj_forLoopAIndex=1
loop
exitwhen bj_forLoopAIndex>a
set t2=CreateTimer()
set ht2=GetHandleId(t2)
call SaveInteger(udg_hash,ht2,0,ht)
if b==1 then
set dmg=s__SpiderX[random_list[bj_forLoopAIndex-1]]
set hp=s__SpiderY[random_list[bj_forLoopAIndex-1]]
elseif b==2 then
set dmg=s__TrollX[random_list[bj_forLoopAIndex-1]]
set hp=s__TrollY[random_list[bj_forLoopAIndex-1]]
elseif b==3 then
set dmg=s__IetiX[random_list[bj_forLoopAIndex-1]]
set hp=s__IetiY[random_list[bj_forLoopAIndex-1]]
elseif b==4 then
set dmg=s__RatX[random_list[bj_forLoopAIndex-1]]
set hp=s__RatY[random_list[bj_forLoopAIndex-1]]
elseif b==5 then
set dmg=s__WolfX[random_list[bj_forLoopAIndex-1]]
set hp=s__WolfY[random_list[bj_forLoopAIndex-1]]
elseif b==6 then
set dmg=s__CobX[random_list[bj_forLoopAIndex-1]]
set hp=s__CobY[random_list[bj_forLoopAIndex-1]]
elseif b==7 then
set dmg=s__GolemX[random_list[bj_forLoopAIndex-1]]
set hp=s__GolemY[random_list[bj_forLoopAIndex-1]]
elseif b==8 then
set dmg=s__BanditX[random_list[bj_forLoopAIndex-1]]
set hp=s__BanditY[random_list[bj_forLoopAIndex-1]]
endif
call SaveReal(udg_hash,ht2,'x',dmg)
call SaveReal(udg_hash,ht2,'y',hp)
set bj_lastCreatedEffect=AddSpecialEffect("war3mapImported\\CataclysmFlowerNoflower_Portrait.mdx",dmg,hp)
call SaveEffectHandle(udg_hash,ht2,1,bj_lastCreatedEffect)
call TimerStart(t2,0.1,true,function Quest_New_FlowerS)
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
endif
endif
if questB==1 then
set bj_lastCreatedItem=QuestNew_ResetOrderId(slot)
endif
if QuestStart then
set s__PlayerQuest[id]=s__PlayerQuest[id]+1
call FlushChildHashtable(udg_hash,GetHandleId(BuyItem))
call RemoveItem(BuyItem)
endif
endif
endif
call ResumeTimer(TimerResetQuest)
set Item=null
set BuyItem=null
set t=null
set t2=null
set u=null
set g=null
endfunction

```

### 风险函数 #2 (风险评分: 12)
```jass
function InitGlobals takes nothing returns nothing
local integer i=0
set udg_Drop=0
set udg_AllHeroes=CreateGroup()
set udg_A1=CreateGroup()
set udg_A2=CreateGroup()
set udg_A3=CreateGroup()
set udg_IncomeGroup=CreateGroup()
set udg_INVASION=0
set udg_real=0
set udg_ManaShield=0
set udg_UpgradeTentakle=0
set udg_PlayerOnline=0
set udg_Check=0
set i=0
loop
exitwhen(i>1)
set udg_PlayerNumber[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>1)
set udg_KillAmount[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>1)
set udg_BossAmount[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>1)
set udg_DeathAmount[i]=0
set i=i+1
endloop
set udg_CreepsAmount=0
set i=0
loop
exitwhen(i>1)
set udg_Time[i]=0
set i=i+1
endloop
set udg_RandomBoss=0
set i=0
loop
exitwhen(i>15)
set udg_CheckBoss[i]=false
set i=i+1
endloop
set udg_RageUnits=CreateGroup()
set udg_ModeString=""
set udg_GroupHealWR=CreateGroup()
set udg_EnergyWR=0
set udg_CreepsPlayers=CreateForce()
set i=0
loop
exitwhen(i>1)
set udg_Iss1[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>1)
set udg_Iss2[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>1)
set udg_Iss3[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>1)
set udg_Iss4[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>1)
set udg_Iss5[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>1)
set udg_Iss6[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>1)
set udg_Iss7[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>1)
set udg_Iss8[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>1)
set udg_Iss9[i]=0
set i=i+1
endloop
set udg_Quest=true
set udg_KataAtk=CreateGroup()
set udg_ug=CreateGroup()
set udg_ShamanItem=CreateGroup()
set udg_KrabUlt=false
set udg_CrabSkillNum=0
set i=0
loop
exitwhen(i>8)
set udg_Plants[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>8)
set udg_Silver[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>8)
set udg_Sphere[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>8)
set udg_Kladb[i]=0
set i=i+1
endloop
set udg_DiabolicBoots=CreateGroup()
set udg_NagaBoss=0
set udg_LumberLimit=0
set udg_SukkubSkilNum=0
set udg_KickNumber=0
set i=0
loop
exitwhen(i>10)
set udg_Scel[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>8)
set udg_FriendFire[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>8)
set udg_PlayerExp[i]=0
set i=i+1
endloop
set udg_KickGroup=CreateForce()
set udg_PN=0
set udg_AgiSniper=0
set i=0
loop
exitwhen(i>8)
set udg_AlchemyPoints[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>8)
set udg_ABoolean1[i]=false
set i=i+1
endloop
set i=0
loop
exitwhen(i>8)
set udg_ABoolean2[i]=false
set i=i+1
endloop
set i=0
loop
exitwhen(i>8)
set udg_ABoolean3[i]=false
set i=i+1
endloop
set i=0
loop
exitwhen(i>8)
set udg_ABoolean4[i]=false
set i=i+1
endloop
set i=0
loop
exitwhen(i>8)
set udg_ABoolean5[i]=false
set i=i+1
endloop
set i=0
loop
exitwhen(i>8)
set udg_ABoolean6[i]=false
set i=i+1
endloop
set i=0
loop
exitwhen(i>8)
set udg_ABoolean7[i]=false
set i=i+1
endloop
set i=0
loop
exitwhen(i>8)
set udg_ABoolean8[i]=false
set i=i+1
endloop
set i=0
loop
exitwhen(i>8)
set udg_ABoolean9[i]=false
set i=i+1
endloop
set udg_CountAttackers=0
set udg_AttackersBoolean=false
set i=0
loop
exitwhen(i>8)
set udg_Mask[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>30)
set udg_lvlicon[i]=""
set i=i+1
endloop
set i=0
loop
exitwhen(i>30)
set udg_lvlname[i]=""
set i=i+1
endloop
set udg_Drop2=0
set udg_AttackTimer=CreateTimer()
set udg_SunArmor=0
set udg_SWindow=DialogCreate()
set i=0
loop
exitwhen(i>2)
set udg_SMission[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>2)
set udg_SQuest[i]=0
set i=i+1
endloop
set udg_PartizanStr=0
set i=0
loop
exitwhen(i>15)
set udg_RandomEventsText[i]=""
set i=i+1
endloop
set i=0
loop
exitwhen(i>5)
set udg_RandomEvents[i]=0
set i=i+1
endloop
set udg_TeleGhoul=CreateGroup()
set udg_ZveroboyStr=0
set udg_IncomeGroup2=CreateGroup()
set udg_StormBoltGrifon=0
set udg_GrobNumber=0
set udg_GrobRegen=false
set udg_KenariusNum=0
set i=0
loop
exitwhen(i>5)
set udg_SpawnTimer[i]=CreateTimer()
set i=i+1
endloop
set udg_WardenAgi=0
set udg_NatrezimR=false
set i=0
loop
exitwhen(i>1)
set udg_SfinksZapret[i]=false
set i=i+1
endloop
set udg_TyraelGroup=CreateGroup()
set udg_SecretItemCount=0
set udg_SellPlantsTimer=CreateTimer()
set i=0
loop
exitwhen(i>8)
set udg_HeroExp[i]=0
set i=i+1
endloop
set udg_SecretBandit=0
set udg_SecretAlkapSet=false
set i=0
loop
exitwhen(i>8)
set udg_HeroGold[i]=0
set i=i+1
endloop
set udg_r=0
set udg_AxeW=false
set udg_AxeE=0
set udg_Mishka=0
set udg_ListTimer=CreateTimer()
set udg_Mode=0
set udg_DruidGroup=CreateGroup()
set udg_FlameOrcTimer=CreateTimer()
set udg_FlameOrcQTimer=CreateTimer()
set udg_FlameOrcQ=0
set udg_FlameOrcReal=0
set udg_EvilPlayer=null
set udg_CheckEvil=0
set udg_EvilTimer=CreateTimer()
set udg_EPTimer=CreateTimer()
set udg_EPincome=0
set udg_CheckBossSkillsGroup=CreateGroup()
set udg_BossRegen=CreateGroup()
set udg_BossRegenTimer=CreateTimer()
set i=0
loop
exitwhen(i>8)
set udg_MeshochekCount[i]=0
set i=i+1
endloop
set udg_SpiritE=CreateGroup()
set udg_RHCheck=CreateForce()
set udg_RHLogic=false
set udg_WavesCount=0
set udg_CDRandomNumber=0
set udg_CDCheck=CreateForce()
set udg_CDFastStart=0
set udg_IspTimer=CreateTimer()
set udg_MoveTimer=CreateTimer()
set i=0
loop
exitwhen(i>8)
set udg_DragonSlayerItem[i]=0
set i=i+1
endloop
set udg_MurkyD=0
set udg_MurkyRTimer=CreateTimer()
set i=0
loop
exitwhen(i>8)
set udg_ReflectDmg[i]=0
set i=i+1
endloop
set udg_ShopTimer=CreateTimer()
set i=0
loop
exitwhen(i>8)
set udg_MeshochekCheck[i]=0
set i=i+1
endloop
set udg_MoargDTimer=CreateTimer()
set udg_MoargD=0
set udg_MoargDLimit=0
set udg_MoargEconst=0
set udg_MoargEGroup=CreateGroup()
set udg_KITimer=CreateTimer()
set udg_CaptainD=false
set udg_r2=0
set i=0
loop
exitwhen(i>8)
set udg_BeltOfDeath[i]=0
set i=i+1
endloop
set udg_EssenceOfLifeGroup=CreateGroup()
set udg_BatLogic=false
set udg_BatLogicW=false
set udg_BatDmgW=1.00
set udg_BersDMG=0
set udg_BatEReal=0
set udg_RockDefenderE=0
set udg_RockDefender50=false
set udg_ThiefLogic=false
set udg_ZCount=0
set udg_ZLogic=false
set i=0
loop
exitwhen(i>8)
set udg_HeroResTime[i]=0
set i=i+1
endloop
set udg_WitchDTimer=CreateTimer()
set udg_WitchD=0
set udg_ListGroup=CreateGroup()
set i=0
loop
exitwhen(i>5)
set udg_LvlItemLogic[i]=false
set i=i+1
endloop
set udg_StartQuests=0
set i=0
loop
exitwhen(i>9)
set udg_Quests[i]=CreateForce()
set i=i+1
endloop
set i=0
loop
exitwhen(i>12)
set udg_Quest4Kills[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>8)
set udg_QTrolls[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>8)
set udg_QGolems[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>8)
set udg_QBeorns[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>8)
set udg_QKobolds[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>8)
set udg_QGhouls[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>8)
set udg_QNaga[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>8)
set udg_QMurlocs[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>8)
set udg_QLobster[i]=0
set i=i+1
endloop
set udg_LastQuest=false
set udg_LastQuestReward=false
set udg_AnciestSealGroup=CreateGroup()
set i=0
loop
exitwhen(i>3)
set udg_WitchSkillQ[i]=CreateGroup()
set i=i+1
endloop
set udg_HARDSET=0
set udg_MoargR=false
set udg_AnciestSealTimer=CreateTimer()
set udg_ForpostLogic=false
set udg_CrabD=0
set udg_RitualBlade=500.00
set i=0
loop
exitwhen(i>5)
set udg_Quests2[i]=CreateForce()
set i=i+1
endloop
set udg_AdriaHandLvl=1
set i=0
loop
exitwhen(i>8)
set udg_KGolems[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>8)
set udg_KTrees[i]=0
set i=i+1
endloop
set udg_LastQuest2=false
set i=0
loop
exitwhen(i>8)
set udg_KQuest3[i]=true
set i=i+1
endloop
set i=0
loop
exitwhen(i>8)
set udg_KQuest4[i]=0
set i=i+1
endloop
set udg_ReplayWindow=DialogCreate()
set udg_WitchDBonus=0
set udg_WitchDStucks=0
set udg_ZavodCheck=CreateGroup()
set udg_PortLogic=true
set i=0
loop
exitwhen(i>3)
set udg_CrowLeveling[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>10)
set udg_CrowExp[i]=0
set i=i+1
endloop
set udg_CrowW=CreateGroup()
set udg_PandoraBox=false
set udg_LeoricE=0
set udg_LeoricLogic=false
set udg_Timer01s=CreateTimer()
set udg_CrowRLogic=false
set udg_ChampionSpearLvl=1
set udg_NatureGuardianW=CreateGroup()
set udg_SpiritQ=CreateGroup()
set udg_DarkEyeGroup=CreateGroup()
set udg_DeathNecklaceGroup=CreateGroup()
set udg_UpItemsStone=0
set i=0
loop
exitwhen(i>10)
set udg_ItemComplectGroup[i]=CreateGroup()
set i=i+1
endloop
set udg_RedTalismanGroup=CreateGroup()
set udg_HammerGroup=CreateGroup()
set udg_SkillsCheck=CreateGroup()
set udg_VoronsTower=0
set i=0
loop
exitwhen(i>1)
set udg_BossSpawnLvl[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>1)
set udg_Damage[i]=0
set i=i+1
endloop
set udg_DamageTeam=CreateGroup()
set i=0
loop
exitwhen(i>8)
set udg_ABoolean10[i]=false
set i=i+1
endloop
set i=0
loop
exitwhen(i>8)
set udg_ABoolean11[i]=false
set i=i+1
endloop
set i=0
loop
exitwhen(i>8)
set udg_ABoolean12[i]=false
set i=i+1
endloop
set udg_HELLSET=0
set i=0
loop
exitwhen(i>1)
set udg_BilderQuestAl[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>1)
set udg_BilderQuestOrc[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>1)
set udg_BilderQuestOgr[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>5)
set udg_SpawnTimerforWave[i]=CreateTimer()
set i=i+1
endloop
set i=0
loop
exitwhen(i>1)
set udg_HelldamageNEW[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>1)
set udg_HellLife[i]=0
set i=i+1
endloop
set udg_String=""
set i=0
loop
exitwhen(i>1)
set udg_CheckLimitSpells[i]=0
set i=i+1
endloop
set udg_HellLaw=false
set udg_WaterElemZapetus=0
set udg_UDex=0
set i=0
loop
exitwhen(i>1)
set udg_UnitIndexLock[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>1)
set udg_UDexPrev[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>1)
set udg_UDexNext[i]=0
set i=i+1
endloop
set udg_UnitIndexEvent=0
set udg_UDexRecycle=0
set udg_UnitIndexerEnabled=false
set udg_UDexWasted=0
set udg_UDexGen=0
set udg_DamageTypeExplosive=0
set udg_DamageTypeCriticalStrike=0
set udg_DamageTypeHeal=0
set udg_DamageTypeReduced=0
set udg_DamageTypeBlocked=0
set udg_DAMAGE_FACTOR_BRACERS=0
set udg_DAMAGE_FACTOR_ELUNES=0
set udg_DAMAGE_FACTOR_ETHEREAL=0
set udg_DamageEventAOE=0
set udg_DamageEventLevel=0
set udg_AfterDamageEvent=0
set udg_DamageEvent=0
set udg_AOEDamageEvent=0
set udg_DamageModifierEvent=0
set udg_DamageEventAmount=0
set udg_DamageEventPrevAmt=0
set udg_DamageEventOverride=false
set udg_NextDamageOverride=false
set udg_DamageEventType=0
set i=0
loop
exitwhen(i>1)
set udg_LastDmgPrevType[i]=0
set i=i+1
endloop
set udg_NextDamageType=0
set udg_DamageEventsWasted=0
set udg_DmgEvRecursionN=0
set udg_DmgEvRunning=false
set udg_DmgEvStarted=false
set udg_IsDamageSpell=false
set i=0
loop
exitwhen(i>1)
set udg_LastDmgWasSpell[i]=false
set i=i+1
endloop
set udg_LastDamageHP=0
set udg_DmgEvTimer=CreateTimer()
set i=0
loop
exitwhen(i>1)
set udg_LastDmgPrevAmount[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>1)
set udg_LastDmgValue[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>1)
set udg_HideDamageFrom[i]=false
set i=i+1
endloop
set i=0
loop
exitwhen(i>1)
set udg_UnitDamageRegistered[i]=false
set i=i+1
endloop
set udg_DmgEvMana=0
set udg_DmgEvMSlvl=0
set udg_DmgEvManaMult=0
set i=0
loop
exitwhen(i>1)
set udg_HeroGoldMax[i]=0
set i=i+1
endloop
set udg_after20min=false
set i=0
loop
exitwhen(i>1)
set udg_GunAvengereLimit[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>1)
set udg_MagichkaInt[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>1)
set udg_MinusDamage[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>1)
set udg_DamageQuiestBilder[i]=0
set i=i+1
endloop
set udg_Setstart=false
set udg_DarkSgustokQ=CreateGroup()
set i=0
loop
exitwhen(i>1)
set udg_DamageEngineService[i]=0
set i=i+1
endloop
set udg_WarboosSpellLogic=false
set udg_RockDefenderLE=false
set udg_RedKill=false
set udg_SlaveSucLogic=false
set udg_SetEnd=false
set i=0
loop
exitwhen(i>1)
set udg_AbuseAttack[i]=0
set i=i+1
endloop
set udg_dmg=0
set udg_Rifle50=0
set udg_RifleE=0
set i=0
loop
exitwhen(i>1)
set udg_RifleR[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>5)
set udg_RifleLogic[i]=false
set i=i+1
endloop
set udg_RifleAttackBoost=0
set udg_DemolitronItem=0
set i=0
loop
exitwhen(i>1)
set udg_ScorpionMutation[i]=0
set i=i+1
endloop
set udg_ScorpionBloodstone=0
set udg_ScorpionLvlE=0
set udg_GroupOgreForge=CreateGroup()
set udg_ScorpionKills=0
set udg_MatrixGroup=CreateGroup()
set i=0
loop
exitwhen(i>1)
set udg_MatrixDamage[i]=0
set i=i+1
endloop
set udg_HardestLogic=false
set udg_TankPlasmaBatteryLogic=false
set udg_Realskill=0
set udg_BarbarionE=0
set udg_SetDamageTimer=0
set i=0
loop
exitwhen(i>1)
set udg_DamageEngineLogick[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>1)
set udg_DEItemLogic[i]=false
set i=i+1
endloop
set udg_MagnR=CreateTimer()
set udg_KovenLogic=false
set udg_BarbarianW=false
set udg_BarbarionStacks=0
set udg_BarbarianELogic=false
set i=0
loop
exitwhen(i>1)
set udg_PartizanLimit[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>10)
set udg_ThingExp[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>3)
set udg_ThingLeveling[i]=0
set i=i+1
endloop
set udg_ThingHP=0
set udg_ThingNumber=0
set udg_Timer5min=CreateTimer()
set udg_TaurenPristT=CreateTimer()
set udg_TaurenPristHeal=0
set udg_TaurenPristR=CreateTimer()
set udg_TimerWave=CreateTimer()
set i=0
loop
exitwhen(i>1)
set udg_reals[i]=0
set i=i+1
endloop
set udg_ThingT=CreateTimer()
set udg_SpellBreaker50=false
set udg_SpellBreakerRdmg=0
set udg_SpellBreakerR=false
set udg_Minutes=0
set i=0
loop
exitwhen(i>8)
set udg_Talante[i]=0
set i=i+1
endloop
set udg_FlameOrcD=false
set udg_Miasm=0
set udg_QuestNumber=0
set udg_Quest3Portal=false
set i=0
loop
exitwhen(i>1)
set udg_ReactorAganim[i]=false
set i=i+1
endloop
set udg_Quest3UG=CreateGroup()
set udg_FireLordDeath=0
set udg_FireLordFdamage=0
set i=0
loop
exitwhen(i>1)
set udg_SwordAgi[i]=0
set i=i+1
endloop
set udg_StoneHeal=CreateGroup()
set udg_ug_Regen=CreateGroup()
set udg_Timer25ms=CreateTimer()
set i=0
loop
exitwhen(i>8)
set udg_Frostmourne[i]=0
set i=i+1
endloop
set udg_noSplash=false
set udg_ThingBonus=0
set udg_after17min=false
set i=0
loop
exitwhen(i>1)
set udg_TrophyNeed1[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>10)
set udg_Looting[i]=1.00
set i=i+1
endloop
set i=0
loop
exitwhen(i>1)
set udg_TrophyNeed3[i]=0
set i=i+1
endloop
set i=0
loop
exitwhen(i>1)
set udg_TrophyNeed2[i]=0
set i=i+1
endloop
set udg_ForestBoss=0
set udg_BattlefieldUG=CreateGroup()
set udg_TaksGroup=CreateGroup()
set i=0
loop
exitwhen(i>1)
set udg_QuestPoints[i]=0
set i=i+1
endloop
set udg_UGaoeAttack=CreateGroup()
set udg_DefFort=false
set udg_Drop3=0
set udg_Drop4=0
set udg_behelit=CreateGroup()
set udg_UnordinaryUnit=CreateGroup()
set udg_BuyItem=false
set udg_Start=false
set udg_HellDamageL=false
set i=0
loop
exitwhen(i>8)
set udg_SReligion[i]=0
set i=i+1
endloop
set udg_HeroBuild=CreateGroup()
set udg_destcount=0
set udg_BossG=CreateGroup()
endfunction

```

### 风险函数 #3 (风险评分: 12)
```jass
function Trig_ArtaSkills_Actions takes nothing returns nothing
local unit hero=GetTriggerUnit()
local integer ID=GetPlayerId(GetOwningPlayer(hero))+1
local unit u
local real xh=GetUnitX(hero)
local real yh=GetUnitY(hero)
local real x
local real y
local real x1
local real y1
local real dmg
local real r
local real z
local timer t
local integer ht
if GetSpellAbilityId()=='A0B9' then
set x=GetSpellTargetX()
set y=GetSpellTargetY()
set u=CreateUnit(Player(ID-1),'h058',xh,yh,bj_RADTODEG*Atan2(y-yh,x-xh))
call KnockBackUnit(u,1800,2.1,bj_RADTODEG*Atan2(y-yh,x-xh),0.03)
set t=CreateTimer()
set ht=GetHandleId(t)
call SaveUnitHandle(udg_hash,ht,0,hero)
call SaveUnitHandle(udg_hash,ht,1,u)
call SaveReal(udg_hash,ht,2,2.13)
call SaveGroupHandle(udg_hash,ht,3,CreateGroup())
call TimerStart(t,0.03,true,function ArtaQ)
endif
if GetSpellAbilityId()=='A067' then
call SetPlayerTechResearchedSwap('R00O',GetUnitAbilityLevelSwapped('A067',GetSpellAbilityUnit()),GetOwningPlayer(GetSpellAbilityUnit()))
if GetUnitAbilityLevel(hero,'A0BQ')==1 then
set dmg=0.75*Summ_Attack(hero)
else
set dmg=GetHeroStr(hero,true)
endif
set x=GetSpellTargetX()
set y=GetSpellTargetY()
set u=CreateUnit(GetOwningPlayer(hero),'h01G',x,y,GetUnitFacing(hero))
call UnitAddAbility(u,'A007')
call SummonStats(false,0,R2I(dmg),u,hero)
call UnitRemoveAbility(u,'A007')
call IssuePointOrder(u,"attackground",x,y)
call UnitApplyTimedLife(u,'BTLF',0.75)
set bj_forLoopAIndex=1
loop
exitwhen bj_forLoopAIndex>2
set r=(100.+GetRandomReal(-20.,30.))
set z=GetUnitFacing(hero)+GetRandomReal(-20.,20.)
set x1=x+r*Cos(z*bj_DEGTORAD)
set y1=y+r*Sin(z*bj_DEGTORAD)
set u=CreateUnit(GetOwningPlayer(hero),'h01G',x,y,GetUnitFacing(hero))
call UnitAddAbility(u,'A007')
call SummonStats(false,0,R2I(dmg),u,hero)
call UnitRemoveAbility(u,'A007')
call IssuePointOrder(u,"attackground",x1,y1)
call UnitApplyTimedLife(u,'BTLF',0.75)
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
set bj_forLoopAIndex=1
loop
exitwhen bj_forLoopAIndex>3
set r=(220.+GetRandomReal(-20.,30.))
set z=GetUnitFacing(hero)+GetRandomReal(-25.,25.)
set x1=x+r*Cos(z*bj_DEGTORAD)
set y1=y+r*Sin(z*bj_DEGTORAD)
set u=CreateUnit(GetOwningPlayer(hero),'h01G',x,y,GetUnitFacing(hero))
call UnitAddAbility(u,'A007')
call SummonStats(false,0,R2I(dmg),u,hero)
call UnitRemoveAbility(u,'A007')
call IssuePointOrder(u,"attackground",x1,y1)
call UnitApplyTimedLife(u,'BTLF',0.75)
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
set bj_forLoopAIndex=1
loop
exitwhen bj_forLoopAIndex>4
set r=(350.+GetRandomReal(-20.,30.))
set z=GetUnitFacing(hero)+GetRandomReal(-35.,35.)
set x1=x+r*Cos(z*bj_DEGTORAD)
set y1=y+r*Sin(z*bj_DEGTORAD)
set u=CreateUnit(GetOwningPlayer(hero),'h01G',x,y,GetUnitFacing(hero))
call UnitAddAbility(u,'A007')
call SummonStats(false,0,R2I(dmg),u,hero)
call UnitRemoveAbility(u,'A007')
call IssuePointOrder(u,"attackground",x1,y1)
call UnitApplyTimedLife(u,'BTLF',0.75)
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
set bj_forLoopAIndex=1
loop
exitwhen bj_forLoopAIndex>5
set r=(500.+GetRandomReal(-20.,30.))
set z=GetUnitFacing(hero)+GetRandomReal(-40.,40.)
set x1=x+r*Cos(z*bj_DEGTORAD)
set y1=y+r*Sin(z*bj_DEGTORAD)
set u=CreateUnit(GetOwningPlayer(hero),'h01G',x,y,GetUnitFacing(hero))
call UnitAddAbility(u,'A007')
call SummonStats(false,0,R2I(dmg),u,hero)
call UnitRemoveAbility(u,'A007')
call IssuePointOrder(u,"attackground",x1,y1)
call UnitApplyTimedLife(u,'BTLF',0.75)
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
set bj_forLoopAIndex=1
loop
exitwhen bj_forLoopAIndex>6
set r=(650.+GetRandomReal(-20.,30.))
set z=GetUnitFacing(hero)+GetRandomReal(-45.,45.)
set x1=x+r*Cos(z*bj_DEGTORAD)
set y1=y+r*Sin(z*bj_DEGTORAD)
set u=CreateUnit(GetOwningPlayer(hero),'h01G',x,y,GetUnitFacing(hero))
call UnitAddAbility(u,'A007')
call SummonStats(false,0,R2I(dmg),u,hero)
call UnitRemoveAbility(u,'A007')
call IssuePointOrder(u,"attackground",x1,y1)
call UnitApplyTimedLife(u,'BTLF',0.75)
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
set bj_forLoopAIndex=1
loop
exitwhen bj_forLoopAIndex>7
set r=(800.+GetRandomReal(-20.,30.))
set z=GetUnitFacing(hero)+GetRandomReal(-45.,45.)
set x1=x+r*Cos(z*bj_DEGTORAD)
set y1=y+r*Sin(z*bj_DEGTORAD)
set u=CreateUnit(GetOwningPlayer(hero),'h01G',x,y,GetUnitFacing(hero))
call UnitAddAbility(u,'A007')
call SummonStats(false,0,R2I(dmg),u,hero)
call UnitRemoveAbility(u,'A007')
call IssuePointOrder(u,"attackground",x1,y1)
call UnitApplyTimedLife(u,'BTLF',0.75)
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
set bj_forLoopAIndex=1
loop
exitwhen bj_forLoopAIndex>7
set r=(950.+GetRandomReal(-20.,30.))
set z=GetUnitFacing(hero)+GetRandomReal(-45.,45.)
set x1=x+r*Cos(z*bj_DEGTORAD)
set y1=y+r*Sin(z*bj_DEGTORAD)
set u=CreateUnit(GetOwningPlayer(hero),'h01G',x,y,GetUnitFacing(hero))
call UnitAddAbility(u,'A007')
call SummonStats(false,0,R2I(dmg),u,hero)
call UnitRemoveAbility(u,'A007')
call IssuePointOrder(u,"attackground",x1,y1)
call UnitApplyTimedLife(u,'BTLF',0.75)
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
endif
set hero=null
set u=null
set t=null
endfunction

```

### 风险函数 #4 (风险评分: 12)
```jass
function Trig_PartizanSkills_Actions takes nothing returns nothing
local unit caster=GetTriggerUnit()
local integer h=GetHandleId(caster)
local integer ihh=LoadInteger(udg_hash,h,5)
local real x=0
local real y=0
local real x1
local real y1
local real r
local real z
local group g
local integer i=0
local integer a=0
local integer hp=0
local integer dmg=0
local integer drop=GetPlayerId(GetOwningPlayer(caster))+1
local integer str
local integer int
local integer name
local timer t
local integer ht
local integer Loop
local unit u
if GetSpellAbilityId()=='A0AO' then
if udg_Mode==4 then
if udg_PartizanLimit[1]==2 then
set caster=null
return
else
set udg_PartizanLimit[1]=(udg_PartizanLimit[1]+1)
endif
else
endif
if udg_Talante[drop]==1 then
set x=(20*GetUnitAbilityLevel(caster,'A0AO')+GetHeroStr(caster,true))*LoadReal(udg_hash,h,4)
call TempStats(caster,0,0,0,R2I(x),0,0,20.)
endif
if udg_Talante[drop]==2 then
set int=GetHeroInt(caster,true)-R2I(0.5*s__Heroes_TempInt[sHero[ihh]])
set str=GetHeroStr(caster,true)-R2I(0.5*s__Heroes_TempStr[sHero[ihh]])
set hp=R2I(3.*I2R(str)+3.*I2R(int))
set dmg=R2I(0.35*I2R(int))
if GetHeroLevel(caster)>=50 then
set hp=hp*2
endif
endif
set x=GetUnitX(caster)
set y=GetUnitY(caster)
set Loop=1
set r=50.
loop
exitwhen Loop>4
set x1=x+250.*Cos((GetUnitFacing(caster)+180.+Loop*45.-90.)*bj_DEGTORAD)
set y1=y+250.*Sin((GetUnitFacing(caster)+180.+Loop*45.-90.)*bj_DEGTORAD)
set name=udg_PartizanSummon[GetRandomInt(1,4+GetUnitAbilityLevel(caster,'A0AO'))]
if ModuloInteger(Loop,2)==0 then
set z=r
else
set z=0.
endif
call SpawnPartizanUnit(caster,name,x1,y1,GetUnitFacing(caster),z,hp,dmg,drop)
set Loop=Loop+1
endloop
if GetUnitAbilityLevel(caster,'A0JE')==1 then
set Loop=1
loop
exitwhen Loop>2
set x1=x+350.*Cos((GetUnitFacing(caster)+45.+Loop*90.)*bj_DEGTORAD)
set y1=y+350.*Sin((GetUnitFacing(caster)+45.+Loop*90.)*bj_DEGTORAD)
set name=udg_PartizanSummon[GetRandomInt(1,4+GetUnitAbilityLevel(caster,'A0AO'))]
call SpawnPartizanUnit(caster,name,x1,y1,GetUnitFacing(caster),r,hp,dmg,drop)
set Loop=Loop+1
endloop
set Loop=1
loop
exitwhen Loop>2
set x1=x+300.*Cos((GetUnitFacing(caster)+45.+Loop*90.)*bj_DEGTORAD)
set y1=y+300.*Sin((GetUnitFacing(caster)+45.+Loop*90.)*bj_DEGTORAD)
set name=udg_PartizanSummon[GetRandomInt(1,4+GetUnitAbilityLevel(caster,'A0AO'))]
call SpawnPartizanUnit(caster,name,x1,y1,GetUnitFacing(caster),r,hp,dmg,drop)
set Loop=Loop+1
endloop
set Loop=1
loop
exitwhen Loop>2
set x1=x+300.*Cos((GetUnitFacing(caster)-90.+Loop*180.)*bj_DEGTORAD)
set y1=y+300.*Sin((GetUnitFacing(caster)-90.+Loop*180.)*bj_DEGTORAD)
set name=udg_PartizanSummon[GetRandomInt(1,4+GetUnitAbilityLevel(caster,'A0AO'))]
call SpawnPartizanUnit(caster,name,x1,y1,GetUnitFacing(caster),0.,hp,dmg,drop)
set Loop=Loop+1
endloop
endif
endif
if GetSpellAbilityId()=='A0AN' then
set x=GetUnitX(caster)
set y=GetUnitY(caster)
set u=CreateUnit(GetOwningPlayer(caster),'h009',x,y,bj_UNIT_FACING)
call UnitAddAbility(u,'Aivs')
call IssueTargetOrder(u,"invisibility",GetSpellAbilityUnit())
call UnitApplyTimedLife(u,'BTLF',.75)
if udg_Talante[drop]==1 then
call SetUnitState(caster,UNIT_STATE_LIFE,GetUnitState(caster,UNIT_STATE_LIFE)+GetUnitState(caster,UNIT_STATE_MAX_LIFE)*(0.07+0.03*GetUnitAbilityLevel(caster,'A0AN')))
endif
set Loop=1
loop
exitwhen Loop>12
set u=CreateUnit(GetOwningPlayer(caster),'h026',x,y,30.*Loop)
set x1=x+500.*Cos(30.*Loop*bj_DEGTORAD)
set y1=y+500.*Sin(30.*Loop*bj_DEGTORAD)
call IssuePointOrder(u,"attack",x,y)
call UnitApplyTimedLife(u,'BTLF',8.)
set Loop=Loop+1
endloop
endif
if GetSpellAbilityId()=='A0AP' then
set x=GetSpellTargetX()
set y=GetSpellTargetY()
set g=CreateGroup()
set u=CreateUnit(GetOwningPlayer(caster),'h027',x,y,GetRandomReal(0,360))
call GroupAddUnit(g,u)
set Loop=1
loop
exitwhen Loop>12
set r=GetRandomReal(100.00,300.00)
set z=GetRandomReal(0,360)
set x1=x+r*Cos(z*bj_DEGTORAD)
set y1=y+r*Sin(z*bj_DEGTORAD)
set u=CreateUnit(GetOwningPlayer(caster),'h027',x1,y1,GetRandomReal(0,360))
call UnitRemoveAbility(u,'A0AR')
call UnitRemoveAbility(u,'A0AS')
call GroupAddUnit(g,u)
set Loop=Loop+1
endloop
set t=CreateTimer()
set ht=GetHandleId(t)
call SaveUnitHandle(udg_hash,ht,0,caster)
call SaveInteger(udg_hash,ht,1,15)
call SaveReal(udg_hash,ht,2,x)
call SaveReal(udg_hash,ht,3,y)
call SaveGroupHandle(udg_hash,ht,4,g)
call TimerStart(t,1.,true,function Trig_PartizanSkills_R)
endif
if GetSpellAbilityId()=='A17D' then
set x=GetUnitX(caster)
set y=GetUnitY(caster)
set int=GetHeroInt(caster,true)-R2I(0.5*s__Heroes_TempInt[sHero[ihh]])
set str=GetHeroStr(caster,true)-R2I(0.5*s__Heroes_TempStr[sHero[ihh]])
set hp=R2I(9*I2R(str)+9*I2R(int))
set dmg=R2I(1.05*I2R(int))
if GetHeroLevel(caster)>=50 then
set hp=hp*2
endif
set Loop=1
loop
exitwhen Loop>6
set z=GetUnitFacing(caster)+180.00+Loop*45.00-90.00
set x1=x+250.*Cos(z*bj_DEGTORAD)
set y1=y+250.*Sin(z*bj_DEGTORAD)
set name=udg_PartizanSummon[GetRandomInt(1,4+GetUnitAbilityLevel(caster,'A0AO'))]
call SpawnPartizanUnit(caster,name,x1,y1,GetUnitFacing(caster),30.,hp,dmg,drop)
set Loop=Loop+1
endloop
endif
set caster=null
set u=null
set g=null
set t=null
endfunction

```

### 风险函数 #5 (风险评分: 12)
```jass
function Trig_Tank_Actions takes nothing returns nothing
local unit caster=GetTriggerUnit()
local integer ID=GetPlayerId(GetOwningPlayer(caster))+1
local real dmg
local integer a
local real r
local timer t
local integer ht
local real x
local real y
if GetSpellAbilityId()=='A0DW' then
set dmg=60+60*GetPlayerTechCount(GetOwningPlayer(caster),'R01F',true)+2*GetHeroStr(caster,true)
if GetHeroLevel(caster)>=50 then
set dmg=dmg+0.1*(GetUnitState(caster,UNIT_STATE_MAX_LIFE)-300*GetPlayerTechCount(GetOwningPlayer(caster),'R01E',true))
endif
set r=bj_RADTODEG*Atan2(GetSpellTargetY()-GetUnitY(caster),GetSpellTargetX()-GetUnitX(caster))
set x=GetUnitX(caster)+2000.*Cos(r*bj_DEGTORAD)
set y=GetUnitY(caster)+2000.*Sin(r*bj_DEGTORAD)
set t=CreateTimer()
set ht=GetHandleId(t)
call SaveUnitHandle(Hash,ht,0,caster)
call SaveReal(Hash,ht,0,.96)
call SaveReal(Hash,ht,1,r)
call SaveReal(Hash,ht,2,dmg)
call SaveGroupHandle(Hash,ht,1,CreateGroup())
call SaveGroupHandle(Hash,ht,2,CreateGroup())
call SaveGroupHandle(Hash,ht,3,CreateGroup())
call SaveReal(Hash,ht,4,x)
call SaveReal(Hash,ht,5,y)
call TimerStart(t,0.04,true,function Trig_Tank_W)
endif
if GetSpellAbilityId()=='A0DZ' then
set udg_p=GetUnitLoc(caster)
set udg_p2=GetSpellTargetLoc()
if GetPlayerTechCountSimple('R01G',GetOwningPlayer(caster))==2 then
set a=20
set r=435.
else
set a=14
set r=345.
endif
set bj_forLoopAIndex=1
loop
exitwhen bj_forLoopAIndex>a
set udg_point=PolarProjectionBJ(udg_p2,GetRandomReal(20.00,r),GetRandomDirectionDeg())
call CreateNUnitsAtLoc(1,'h00H',GetOwningPlayer(caster),udg_p,GetUnitFacing(caster))
call F_Attack(bj_lastCreatedUnit,R2I(Summ_Attack(caster)))
call IssuePointOrderLoc(bj_lastCreatedUnit,"attackground",udg_point)
call UnitApplyTimedLife(bj_lastCreatedUnit,'BTLF',0.75)
call RemoveLocation(udg_point)
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
call RemoveLocation(udg_p)
call RemoveLocation(udg_p2)
else
endif
if GetSpellAbilityId()=='A0DX' then
set r=400.+60.*GetHeroLevel(caster)+0.1*GetUnitState(caster,UNIT_STATE_MAX_LIFE)+750.*GetPlayerTechCount(GetOwningPlayer(caster),'R01D',true)
if GetHeroLevel(caster)>=50 then
set r=r+0.1*GetUnitState(caster,UNIT_STATE_MAX_LIFE)
endif
call SetUnitState(caster,UNIT_STATE_LIFE,GetUnitState(caster,UNIT_STATE_LIFE)+r)
endif
if GetSpellAbilityId()=='A0DV' then
if udg_ReactorAganim[ID]then
set a=200+75*GetHeroStr(caster,false)/100
call TempStats(caster,a,0,0,0,0,0,PositiveDuration(caster,10))
endif
call UnitAddAbility(caster,'A0I0')
call SetUnitAbilityLevel(caster,'A0I0',GetPlayerTechCount(GetOwningPlayer(caster),'R01C',true)+1)
set t=CreateTimer()
set ht=GetHandleId(t)
call SaveUnitHandle(udg_hash,ht,0,caster)
if GetPlayerTechCountSimple('R01G',GetOwningPlayer(caster))==2 then
call UnitAddItemByIdSwapped('I0C6',caster)
call SaveBoolean(udg_hash,ht,1,true)
else
call SaveBoolean(udg_hash,ht,1,false)
endif
if UnitHasItemOfTypeBJ(caster,'I0DV')then
call SaveBoolean(udg_hash,GetHandleId(caster),StringHash("TankBattery"),true)
call SaveBoolean(udg_hash,ht,2,true)
else
call SaveBoolean(udg_hash,ht,2,false)
endif
call TimerStart(t,15.,false,function Trig_Tank_Q)
endif
set caster=null
set t=null
endfunction

```

### 风险函数 #6 (风险评分: 12)
```jass
function Trig_PotmSkills_Actions takes nothing returns nothing
local unit caster=GetTriggerUnit()
local unit u
local integer a
local integer b
local integer c
local timer t
local integer ht
local real r
local real x
local real y
local real x1
local real y1
local real angle
local real dmg
if GetSpellAbilityId()=='A0SR' then
set u=GetSpellTargetUnit()
if caster==u then
set r=24
else
set r=16
endif
set a=R2I(1.*GetHeroStr(u,false))
set b=R2I(1.*GetHeroAgi(u,false))
set c=R2I(1.*GetHeroInt(u,false))
call TempStats(u,a,b,c,0,0,0,PositiveDuration(caster,r))
elseif GetSpellAbilityId()=='A0ST' then
set dmg=GetUnitAbilityLevel(caster,'A0ST')*75+2*Summ_Attack(caster)
set x=GetUnitX(caster)
set y=GetUnitY(caster)
set r=Psych_crit(caster,1.,1.)
if GetUnitAbilityLevel(caster,'A0SX')==1 and r>1. then
set dmg=dmg*r
set bj_lastCreatedTextTag=CreateTextTag()
call SetTextTagTextBJ(bj_lastCreatedTextTag,"|c000000FF+"+I2S(R2I(dmg))+"!|r",9.)
call SetTextTagPos(bj_lastCreatedTextTag,x,y,0)
call SetTextTagColorBJ(bj_lastCreatedTextTag,100.,100.,100.,0.)
call SetTextTagVelocityBJ(bj_lastCreatedTextTag,75.,90.)
call SetTextTagSuspended(bj_lastCreatedTextTag,false)
call SetTextTagPermanent(bj_lastCreatedTextTag,false)
call SetTextTagLifespan(bj_lastCreatedTextTag,3.00)
call SetTextTagFadepoint(bj_lastCreatedTextTag,2.00)
endif
set x1=GetSpellTargetX()
set y1=GetSpellTargetY()
set angle=bj_RADTODEG*Atan2(y1-y,x1-x)
set u=CreateUnit(GetOwningPlayer(caster),'h030',x,y,angle)
call KnockBackUnit2(u,1500,1.28,angle,0.04)
set t=CreateTimer()
set ht=GetHandleId(t)
call SaveUnitHandle(udg_hash,ht,0,caster)
call SaveReal(udg_hash,ht,0,1.25)
call SaveUnitHandle(udg_hash,ht,1,u)
call SaveReal(udg_hash,ht,1,dmg)
call SaveGroupHandle(udg_hash,ht,2,CreateGroup())
call TimerStart(t,.25,true,function Trig_PotmSkillQ)
elseif GetSpellAbilityId()=='A0SU' then
set t=CreateTimer()
set ht=GetHandleId(t)
if GetUnitAbilityLevel(caster,'A0SX')==1 then
set r=0.4
set a=20
else
set r=0.8
set a=10
endif
set bj_lastCreatedUnit=CreateUnit(GetOwningPlayer(caster),'h03B',GetSpellTargetX(),GetSpellTargetY(),0.)
call SaveUnitHandle(udg_hash,ht,0,caster)
call SaveInteger(udg_hash,ht,1,a)
call SaveReal(udg_hash,ht,2,GetSpellTargetX())
call SaveReal(udg_hash,ht,3,GetSpellTargetY())
call SaveUnitHandle(udg_hash,ht,4,bj_lastCreatedUnit)
call TimerStart(t,r,true,function Trig_PotmSkillW)
else
endif
set caster=null
set u=null
set t=null
endfunction

```

### 风险函数 #7 (风险评分: 12)
```jass
function Trig_HELLUD_3_boss_Actions takes nothing returns nothing
local real x
local real y
local integer a
local integer h
local unit u
call TriggerAddAction(gg_trg_Set_Damage,function MonolitEffect_DMG)
call TriggerSleepAction(45.)
set bj_forLoopAIndex=1
loop
exitwhen bj_forLoopAIndex>9
set x=GetRandomReal(GetRectMinX(gg_rct_Spawn16),GetRectMaxX(gg_rct_Spawn16))
set y=GetRandomReal(GetRectMinY(gg_rct_Spawn16),GetRectMaxY(gg_rct_Spawn16))
set bj_lastCreatedUnit=CreateUnit(ForcePickRandomPlayer(udg_CreepsPlayers),'u024',x,y,bj_UNIT_FACING)
call GroupAddUnitSimple(bj_lastCreatedUnit,udg_A3)
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
set bj_forLoopAIndex=1
loop
exitwhen bj_forLoopAIndex>2
set x=GetRandomReal(GetRectMinX(gg_rct_Spawn16),GetRectMaxX(gg_rct_Spawn16))
set y=GetRandomReal(GetRectMinY(gg_rct_Spawn16),GetRectMaxY(gg_rct_Spawn16))
set bj_lastCreatedUnit=CreateUnit(ForcePickRandomPlayer(udg_CreepsPlayers),'u025',x,y,bj_UNIT_FACING)
call UnitAddAbilityBJ('A10E',bj_lastCreatedUnit)
call GroupAddUnitSimple(bj_lastCreatedUnit,udg_A3)
call SetUnitAbilityLevelSwapped('A0Z3',bj_lastCreatedUnit,2)
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
set bj_forLoopAIndex=1
loop
exitwhen bj_forLoopAIndex>9
set x=GetRandomReal(GetRectMinX(gg_rct_Spawn73),GetRectMaxX(gg_rct_Spawn73))
set y=GetRandomReal(GetRectMinY(gg_rct_Spawn73),GetRectMaxY(gg_rct_Spawn73))
set bj_lastCreatedUnit=CreateUnit(ForcePickRandomPlayer(udg_CreepsPlayers),'u024',x,y,bj_UNIT_FACING)
call GroupAddUnitSimple(bj_lastCreatedUnit,udg_A3)
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
call TriggerSleepAction(140.00)
set bj_forLoopAIndex=1
loop
exitwhen bj_forLoopAIndex>9
set x=GetRandomReal(GetRectMinX(gg_rct_Spawn16),GetRectMaxX(gg_rct_Spawn16))
set y=GetRandomReal(GetRectMinY(gg_rct_Spawn16),GetRectMaxY(gg_rct_Spawn16))
set bj_lastCreatedUnit=CreateUnit(ForcePickRandomPlayer(udg_CreepsPlayers),'u024',x,y,bj_UNIT_FACING)
call GroupAddUnitSimple(bj_lastCreatedUnit,udg_A3)
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
set bj_forLoopAIndex=1
loop
exitwhen bj_forLoopAIndex>2
set x=GetRandomReal(GetRectMinX(gg_rct_Spawn16),GetRectMaxX(gg_rct_Spawn16))
set y=GetRandomReal(GetRectMinY(gg_rct_Spawn16),GetRectMaxY(gg_rct_Spawn16))
set bj_lastCreatedUnit=CreateUnit(ForcePickRandomPlayer(udg_CreepsPlayers),'u025',x,y,bj_UNIT_FACING)
call UnitAddAbilityBJ('A10E',bj_lastCreatedUnit)
call GroupAddUnitSimple(bj_lastCreatedUnit,udg_A3)
call SetUnitAbilityLevelSwapped('A0Z3',bj_lastCreatedUnit,2)
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
set bj_forLoopAIndex=1
loop
exitwhen bj_forLoopAIndex>12
set x=GetRandomReal(GetRectMinX(gg_rct_Spawn15),GetRectMaxX(gg_rct_Spawn15))
set y=GetRandomReal(GetRectMinY(gg_rct_Spawn15),GetRectMaxY(gg_rct_Spawn15))
set bj_lastCreatedUnit=CreateUnit(ForcePickRandomPlayer(udg_CreepsPlayers),'u024',x,y,bj_UNIT_FACING)
call GroupAddUnitSimple(bj_lastCreatedUnit,udg_A3)
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
set bj_forLoopAIndex=1
loop
exitwhen bj_forLoopAIndex>9
set x=GetRandomReal(GetRectMinX(gg_rct_Spawn73),GetRectMaxX(gg_rct_Spawn73))
set y=GetRandomReal(GetRectMinY(gg_rct_Spawn73),GetRectMaxY(gg_rct_Spawn73))
set bj_lastCreatedUnit=CreateUnit(ForcePickRandomPlayer(udg_CreepsPlayers),'u024',x,y,bj_UNIT_FACING)
call GroupAddUnitSimple(bj_lastCreatedUnit,udg_A3)
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
set bj_forLoopAIndex=1
loop
exitwhen bj_forLoopAIndex>2
set x=GetRandomReal(GetRectMinX(gg_rct_Spawn73),GetRectMaxX(gg_rct_Spawn73))
set y=GetRandomReal(GetRectMinY(gg_rct_Spawn73),GetRectMaxY(gg_rct_Spawn73))
set bj_lastCreatedUnit=CreateUnit(ForcePickRandomPlayer(udg_CreepsPlayers),'u025',x,y,bj_UNIT_FACING)
call UnitAddAbilityBJ('A10E',bj_lastCreatedUnit)
call GroupAddUnitSimple(bj_lastCreatedUnit,udg_A3)
call SetUnitAbilityLevelSwapped('A0Z3',bj_lastCreatedUnit,2)
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
call TriggerSleepAction(60.00)
set bj_forLoopAIndex=1
loop
exitwhen bj_forLoopAIndex>8
set x=GetRandomReal(GetRectMinX(gg_rct_A1),GetRectMaxX(gg_rct_A1))
set y=GetRandomReal(GetRectMinY(gg_rct_A1),GetRectMaxY(gg_rct_A1))
set bj_lastCreatedUnit=CreateUnit(ForcePickRandomPlayer(udg_CreepsPlayers),'u024',x,y,bj_UNIT_FACING)
call UnitAddAbilityBJ('A10E',bj_lastCreatedUnit)
call GroupAddUnitSimple(bj_lastCreatedUnit,udg_A3)
call SetUnitAbilityLevelSwapped('A0Z3',bj_lastCreatedUnit,2)
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
set bj_forLoopAIndex=1
loop
exitwhen bj_forLoopAIndex>3
set x=GetRandomReal(GetRectMinX(gg_rct_A1),GetRectMaxX(gg_rct_A1))
set y=GetRandomReal(GetRectMinY(gg_rct_A1),GetRectMaxY(gg_rct_A1))
set bj_lastCreatedUnit=CreateUnit(ForcePickRandomPlayer(udg_CreepsPlayers),'u025',x,y,bj_UNIT_FACING)
call UnitAddAbilityBJ('A10E',bj_lastCreatedUnit)
call GroupAddUnitSimple(bj_lastCreatedUnit,udg_A3)
call SetUnitAbilityLevelSwapped('A0Z3',bj_lastCreatedUnit,2)
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
set x=GetRandomReal(GetRectMinX(gg_rct_A1),GetRectMaxX(gg_rct_A1))
set y=GetRandomReal(GetRectMinX(gg_rct_A1),GetRectMaxY(gg_rct_A1))
if HardcoreUP30==3 then
set bj_forLoopAIndexEnd=2
else
set bj_forLoopAIndexEnd=1
endif
set bj_forLoopAIndex=1
loop
exitwhen bj_forLoopAIndex>bj_forLoopAIndexEnd
set bj_lastCreatedUnit=CreateUnit(ForcePickRandomPlayer(udg_CreepsPlayers),'u022',x,y,0)
set h=GetHandleId(bj_lastCreatedUnit)
call TriggerRegisterUnitEvent(gg_trg_BossDamaged,bj_lastCreatedUnit,EVENT_UNIT_DAMAGED)
call SaveBoolean(udg_hash,h,'b',true)
call UnitAddAbility(bj_lastCreatedUnit,'A10E')
call SetUnitAbilityLevel(bj_lastCreatedUnit,'A10E',3)
call GroupAddUnit(udg_A3,bj_lastCreatedUnit)
call SetUnitAbilityLevel(bj_lastCreatedUnit,'A0Z3',3)
set bj_lastStartedTimer=CreateTimer()
call SaveUnitHandle(udg_hash,GetHandleId(bj_lastStartedTimer),0,bj_lastCreatedUnit)
call TimerStart(bj_lastStartedTimer,60.,true,function boss_Monolit_Spawn)
set bj_lastStartedTimer=CreateTimer()
call SaveUnitHandle(udg_hash,GetHandleId(bj_lastStartedTimer),0,bj_lastCreatedUnit)
call SaveGroupHandle(udg_hash,GetHandleId(bj_lastStartedTimer),1,CreateGroup())
call TimerStart(bj_lastStartedTimer,0.5,true,function Boss_Monolit_DeathWave)
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
set x=GetRandomReal(GetRectMinX(gg_rct_Spawn73),GetRectMaxX(gg_rct_Spawn73))
set y=GetRandomReal(GetRectMinX(gg_rct_Spawn73),GetRectMaxY(gg_rct_Spawn73))
set u=CreateUnit(ForcePickRandomPlayer(udg_CreepsPlayers),'H04S',x,y,0)
set h=GetHandleId(u)
call GroupAddUnit(G_HeroesIncBoss,u)
call SeekFreeHero(h)
call SeekFreeUnit(h)
call TriggerRegisterUnitEvent(gg_trg_BossDamaged,u,EVENT_UNIT_DAMAGED)
call SaveBoolean(udg_hash,h,'b',true)
call GroupAddUnit(udg_ug_Regen,u)
call SetUnitAbilityLevelSwapped('A0Z3',u,3)
call UnitAddItemByIdSwapped('I0EC',u)
call UnitAddItemByIdSwapped('I09E',u)
call UnitAddItemByIdSwapped('I0AF',u)
call UnitAddItemByIdSwapped('I077',u)
call UnitAddItemByIdSwapped('I0DA',u)
call UnitAddItemByIdSwapped('I0BG',u)
call SetHeroLevelBJ(u,50,false)
call GroupAddUnit(udg_A3,u)
call ForGroup(udg_A1,function Trig_MoveAttackers_Func001A)
call ForGroup(udg_A2,function Trig_MoveAttackers_Func002A)
call ForGroup(udg_A3,function Trig_MoveAttackers_Func003A)
call TriggerSleepAction(100.00)
call TriggerExecute(gg_trg_HELLUD_3)
call TriggerExecute(gg_trg_HELLUD_3)
call DestroyTrigger(gg_trg_HELLUD_3)
call EnableTrigger(gg_trg_WinEnd)
set u=null
endfunction

```

### 风险函数 #8 (风险评分: 10)
```jass
function Trig_BuyHeroJass_Actions takes nothing returns nothing
local unit u=GetEnteringUnit()
local integer id=GetPlayerId(GetOwningPlayer(u))
local integer ID=id+1
local integer h=GetHandleId(u)
local group g=CreateGroup()
local integer a
local boolean No_hero=false
local boolean Is_Mech=false
local string aganime="Герой не имеет улучшения от предмета Реактор"
local integer ihh=0
local timer t
local integer ht
local real x
local real y
local integer i
local integer iuh=SeekFreeUnit(h)
local player pl=Player(id)
local integer tal=0
call GroupEnumUnitsOfPlayer(g,pl,Condition(function BuyHeroJass_Fil_DelOtherHeroes))
call ForGroup(g,function BuyHeroJass_G_DelOtherHeroes)
call GroupClear(g)
set bj_groupEnumTypeId='ewsp'
call GroupEnumUnitsOfPlayer(g,pl,filterGetUnitsOfPlayerAndTypeId)
set bj_lastCreatedUnit=FirstOfGroup(g)
call RemoveUnit(bj_lastCreatedUnit)
call GroupClear(g)
call SaveReal(udg_hash,h,StringHash("HPRegenBonusMult"),1)
set ihh=SeekFreeHero(h)
set PlayerPickHero[id]=true
set LTrophy_1[ID]=1
set LTrophy_2[ID]=1
set LTrophy_3[ID]=1
call GroupAddUnit(udg_ug_Regen,u)
if GetUnitTypeId(u)=='Nbrn' or GetUnitTypeId(u)=='U01O' or GetUnitTypeId(u)=='U02A' or GetUnitTypeId(u)=='U00V' then
set No_hero=true
else
if udg_PlayerExp[ID]>=20000 then
call SummonStats(false,200,10,u,u)
endif
endif
if GetUnitTypeId(u)=='H000' or GetUnitTypeId(u)=='H02T' or GetUnitTypeId(u)=='H04O' then
set Is_Mech=true
set udg_HelldamageNEW[ID]=udg_HelldamageNEW[ID]+0.2
endif
if GetUnitTypeId(u)!='U00V' then
call SaveReal(udg_hash,h,StringHash("HPRegen"),0)
set bj_groupEnumTypeId='ncop'
call GroupEnumUnitsOfPlayer(g,pl,filterGetUnitsOfPlayerAndTypeId)
set bj_lastCreatedUnit=FirstOfGroup(g)
call GroupClear(g)
set bj_lastCreatedUnit=CreateUnit(pl,'h05I',GetUnitX(bj_lastCreatedUnit)+80,GetUnitY(bj_lastCreatedUnit)+80,bj_UNIT_FACING)
set udg_Trophy_build[ID]=bj_lastCreatedUnit
call TriggerRegisterUnitEvent(gg_trg_Trophy_Take,bj_lastCreatedUnit,EVENT_UNIT_PICKUP_ITEM)
call TriggerRegisterUnitEvent(gg_trg_Trophy_Drop,bj_lastCreatedUnit,EVENT_UNIT_DROP_ITEM)
endif
if GetUnitTypeId(u)=='Hblm' then
set udg_GroupHealWR=CreateGroup()
call SaveGroupHandle(udg_hash,h,'W',CreateGroup())
call SaveStr(udg_hash,h,2,"Int")
call SaveStr(udg_hash,h,3,"Range")
call EnableTrigger(gg_trg_TakeEnergy)
call EnableTrigger(gg_trg_FireRing)
call TriggerRegisterUnitEvent(gg_trg_FireRing,u,EVENT_UNIT_SPELL_EFFECT)
set t=CreateTimer()
set ht=GetHandleId(t)
call TimerStart(t,.5,true,function Trig_FireMageW)
endif
if GetUnitTypeId(u)=='E00Q' then
set udg_RockDefender=u
set s__Units_AllBlock[sUnit[iuh]]=s__Units_AllBlock[sUnit[iuh]]+2000
call SaveStr(udg_hash,h,2,"Str")
call SaveStr(udg_hash,h,3,"Melee")
set udg_RockDefenderLE=false
call TriggerRegisterUnitEvent(gg_trg_RockDefender,u,EVENT_UNIT_SPELL_EFFECT)
else
endif
if GetUnitTypeId(u)=='N009' then
set udg_HumanBuilder=u
call SaveStr(udg_hash,h,2,"Int")
call SaveStr(udg_hash,h,3,"Melee")
call IncUnitAbilityLevelSwapped('A14S',u)
call EnableTrigger(gg_trg_SkillsBuilder1)
call EnableTrigger(gg_trg_BilderQuestChoise)
call EnableTrigger(gg_trg_Dead)
call UnitAddAbilityBJ('A10A',udg_HumanBuilder)
set bj_groupEnumTypeId='ncop'
call GroupEnumUnitsOfPlayer(g,pl,filterGetUnitsOfPlayerAndTypeId)
set bj_lastCreatedUnit=FirstOfGroup(g)
call GroupClear(g)
set bj_lastCreatedUnit=CreateUnit(pl,'h04Y',GetUnitX(bj_lastCreatedUnit)-80,GetUnitY(bj_lastCreatedUnit)+80,0.)
call TriggerRegisterUnitEvent(gg_trg_BilderQuestChoise,bj_lastCreatedUnit,EVENT_UNIT_SPELL_EFFECT)
call TriggerRegisterPlayerUnitEvent(gg_trg_Recruting,pl,EVENT_PLAYER_UNIT_TRAIN_FINISH,null)
call TriggerRegisterPlayerUnitEvent(gg_trg_Advance,pl,EVENT_PLAYER_UNIT_RESEARCH_FINISH,null)
call TriggerRegisterPlayerUnitEvent(gg_trg_Fair,pl,EVENT_PLAYER_UNIT_CONSTRUCT_FINISH,null)
call UnitAddItemByIdSwapped('tcas',u)
call UnitAddItemByIdSwapped('mcri',u)
set t=CreateTimer()
set ht=GetHandleId(t)
call SaveInteger(Hash,ht,0,id)
call TimerStart(t,2.,true,function Trig_AlianceTreeLimit)
elseif GetUnitTypeId(u)=='N00G' then
set t=CreateTimer()
set ht=GetHandleId(t)
call SaveInteger(Hash,ht,0,id)
call TimerStart(t,9.2,true,function Trig_Income_Elf)
call SaveGroupHandle(udg_hash,h,StringHash("ElfTower"),CreateGroup())
call IncUnitAbilityLevelSwapped('A14S',u)
call SaveStr(udg_hash,h,2,"Int")
call SaveStr(udg_hash,h,3,"Melee")
set ElfHealTowerSelf=CreateGroup()
set ElfHealTowerG=CreateGroup()
set udg_SpecPoTowers=u
call EnableTrigger(gg_trg_TowerSkills)
call EnableTrigger(gg_trg_IncomeRegister)
call UnitAddItemByIdSwapped('I022',u)
call UnitAddItemByIdSwapped('I023',u)
elseif GetUnitTypeId(u)=='N03T' then
set t=CreateTimer()
set ht=GetHandleId(t)
call SaveInteger(Hash,ht,0,id)
call TimerStart(t,9.7,true,function Trig_IncomeOgr)
set udg_Ogr=u
call SaveStr(udg_hash,h,2,"Str")
call SaveStr(udg_hash,h,3,"Melee")
call IncUnitAbilityLevelSwapped('A14S',u)
call EnableTrigger(gg_trg_IncomeRegisterOgr)
call EnableTrigger(gg_trg_Dead)
call EnableTrigger(gg_trg_OgrUpgrades)
call EnableTrigger(gg_trg_OgreSpell)
call EnableTrigger(gg_trg_RecrutingOgr)
call UnitAddItemByIdSwapped('I027',u)
call UnitAddItemByIdSwapped('I028',u)
set bj_groupEnumTypeId='ncop'
call GroupEnumUnitsOfPlayer(g,pl,filterGetUnitsOfPlayerAndTypeId)
set bj_lastCreatedUnit=FirstOfGroup(g)
call GroupClear(g)
set bj_lastCreatedUnit=CreateUnit(Player(ID-1),'h04Z',GetUnitX(bj_lastCreatedUnit)-80,GetUnitY(bj_lastCreatedUnit)+80,0.)
call TriggerRegisterUnitEvent(gg_trg_BilderQuestOgr,bj_lastCreatedUnit,EVENT_UNIT_SPELL_EFFECT)
call SetPlayerStateBJ(GetOwningPlayer(udg_Ogr),PLAYER_STATE_RESOURCE_FOOD_CAP,50)
elseif GetUnitTypeId(u)=='E008' then
set udg_Murky=u
call SaveStr(udg_hash,h,2,"Agi")
call SaveStr(udg_hash,h,3,"Melee")
set s__Heroes_Type[sHero[ihh]]=4
call TriggerRegisterUnitEvent(gg_trg_MurkySkills,u,EVENT_UNIT_SPELL_EFFECT)
call EnableTrigger(gg_trg_MurkyLvlUp)
call EnableTrigger(gg_trg_MurkyRSummon)
set udg_HeroGold[ID]=udg_HeroGold[ID]+0.2
set udg_HeroGoldMax[ID]=udg_HeroGoldMax[ID]+0.2
set udg_HeroResTime[ID]=udg_HeroResTime[ID]-20.00
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00Mod|r\n+1 лoвкocть зa LvlUP\nCклизкиe oбъятия, +25% к ypoнy/иcцeлeнию\nCкoльзкий тип, дaeт 20/40/60/80/100+25% бaзoвый eд лoвкocти. Пocлe 50 ypoвня дaeт +30% к ypoнy Mod\nBoля к жизни, Mod: 18% шaнc нaнecти 40/80/120/160/200+30%лoвкocть eд мaг ypoнa вpaгaм вoкpyг. Пocлe 50 ypoвня +30%лoвкocть\nДвoйник, пpизывaeт двoйникa имeющий aтaкy, cкopocть aтaки, здopoвьe и зaщитy гepoя. Kaждaя aтaкa cyщecтвa c 50% шaнcoм вызывaeт cpaбaтывaниe Mod. Bpeмя жизни 25 ceк. Пepeзapядкa 60 ceк."
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Death|r\n-10 к вpeмeни вoзpoждeния\nDeath: +20 HP\n+(cилa + лoвкocть)*2 eд ypoн oт Бoмбы, +200% oт дaннoгo знaчeния для Kвapкoвoй бoмбы\nBoля к жизни, Death: +400/800/1200/1600/2000+40(Koл-вo cмepтeй) eд здopoвья нa 30 ceк. Пocлe 50 ypoвня 2*(cилa+лoвкocть) HP oт эффeктa (-)\nДвoйник, пpизывaeт двoйникa имeющий aтaкy, cкopocть aтaки, здopoвьe и зaщитy гepoя, кoтopый пpи cвoeй cмepти взpывaeтcя вызывaя лoжнyю cмepть и нaнocя 50%здopoвья eд ypoнa. Пepeзapядкa 30 ceк."
set s__PlayerStruct_hs3[sPlayer[id]]="|cFFC9AD00Summon|r\n-50% к иcxoдящeмy ypoнy (+)\n+1 cлoт\n+2 cилы и paзyмa зa LvlUP\nCпocoбнocти пpизывaют cлyчaйныx мypлoкoв имeющиx 55%paзyм aтaки и 450%(cилa+paзyм) здopoвья и 10 зaщиты. Пocлe 50 ypoвня oни пoлyчaют 100% пoвышeниe aтaки и +100% здopoвья\nCклизкиe oбъятия, пpизывaeт 4 мypлoкoв нa 30 ceк\nCкoльзкий тип, пpизывaeт 4 мypлoкoв нa 30 ceк\nBoля к жизни, дaeт +10/20/30/40/50+5%бaзoвый eд cилы и paзyмa. Пocлe 50 ypoвня дaeт eщe 25+5%бaзoвый\nCпocoнocть R: Мapш cвoбoды, пpизывaeт дo 20 мypлoкoв"
set tal=3
elseif GetUnitTypeId(u)=='E00X' then
set udg_SpellBreaker=u
call SaveStr(udg_hash,h,2,"Int")
call SaveStr(udg_hash,h,3,"Range")
call TriggerRegisterUnitEvent(gg_trg_SpellBreaker_Skills,u,EVENT_UNIT_SPELL_EFFECT)
call EnableTrigger(gg_trg_SpellBreaker_E)
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00Mod|r\n+2% atk speed зa LvlUP\nБyмepaнг, paз в 1 ceк вызывaeт 1 cpaбaтывaниe Mod в cлyчaйнyю зaдeтyю цeль\nБapьep, вo вpeмя дeйcтвия дaeт 10/20/30/40/50+25%бaзoвoгo paзyмa eд. paзyмa\nМaгичecкиe пoдpывы, пoнижeн ypoн нa 10%, Mod: 10% шaнc вызвaть эффeкь|nKoгepeнция, вo вpeмя дeйcтвия тaкжe иcцeляeт гepoя нa 10+10%paзyм eд. здopoвья/ceк."
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Mage|r\n+1 paзyм зa LvlUP\nБyмepaнг, пoвышeн ypoн нa 75%\nМaгичecкиe пoдpывы, пoвышeн ypoн нa 25%\nKoгepeнция, пoвышeн бaзoвый ypoн в двa paзa"
set s__PlayerStruct_hs3[sPlayer[id]]="|cFFC9AD00Barrier|r\nБyмepaнг, измeнeн ypoн нa -paзyм+10%тeк мaны. Pacxoдyeт 5% тeк мaны\nБapьep, щит тeпepь имeeт бecкoнeчнoe вpeмя дeйcтвия и +100% к здopoвью\nМaгичecкиe пoдpывы, пaccивнo дaeт +2/4/6/8/10+10%paзyм eд MP reg\nKoгepeнция, наносит 10% ypoнa/ceк, однако уменьшен урон взрыва на 50%"
set tal=3
elseif GetUnitTypeId(u)=='E001' then
call SaveStr(udg_hash,h,2,"Agi")
call SaveStr(udg_hash,h,3,"Range")
call TriggerRegisterUnitEvent(gg_trg_HuntressSkills,u,EVENT_UNIT_SPELL_EFFECT)
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00DD|r\nНовая способность: Чакрумы\nТяжелый бросок. Повышает силу атаки на 40/80/120/160/200+75%ловкость в течении 8 сек (усивается на 40% повышение атаки)\nРассечение. Повышен урон на 50%атаки ед\nСпособность 20: Чакрумы Ветров"
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Mage|r\nТяжелый бросок. Страж делает броски стальными чакрумами в случайных противников, нанося по 60/120/180/240/300+55%Ловкость ед. урона цели и 50% урона врагам вокруг. За время каста выпускается 20 чакрумов с инветрвалом в 0.2 сек. Тип урона - Магия.\nРассечение. Повышен урон на 150%ловкость ед\nСпособность 20 уровня: Стена смерти"
set tal=2
elseif GetUnitTypeId(u)=='E00M' then
set s__Heroes_Pass_1sec_1[sHero[ihh]]="Scorpion_1s"
set s__Heroes_Type[sHero[ihh]]=4
call SaveInteger(udg_hash,h,'d',2)
set udg_Scorpion=u
call SaveStr(udg_hash,h,2,"Agi")
call SaveStr(udg_hash,h,3,"Melee")
set udg_HeroGold[id+1]=udg_HeroGold[id+1]+0.15
set udg_HeroGoldMax[id+1]=udg_HeroGoldMax[id+1]+0.15
call EnableTrigger(gg_trg_Scorpion)
call TriggerRegisterUnitEvent(gg_trg_Scorpion,u,EVENT_UNIT_SPELL_EFFECT)
call EnableTrigger(gg_trg_ScorpionMut)
set bj_groupEnumTypeId='ncop'
call GroupEnumUnitsOfPlayer(g,pl,filterGetUnitsOfPlayerAndTypeId)
set bj_lastCreatedUnit=FirstOfGroup(g)
call GroupClear(g)
set bj_lastCreatedUnit=CreateUnit(pl,'h055',GetUnitX(bj_lastCreatedUnit)-80,GetUnitY(bj_lastCreatedUnit)+80,bj_UNIT_FACING)
elseif GetUnitTypeId(u)=='E00D' then
set s__Heroes_Type[sHero[ihh]]=4
call SaveStr(udg_hash,h,2,"Int")
call SaveStr(udg_hash,h,3,"Range")
call TriggerRegisterUnitEvent(gg_trg_Dryad,u,EVENT_UNIT_SPELL_EFFECT)
set udg_HeroGold[id+1]=udg_HeroGold[id+1]+0.2
set udg_HeroGoldMax[id+1]=udg_HeroGoldMax[id+1]+0.2
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00Regen|r\n+1 cлoт\n-10% к вxoдящeмy ypoнy (+)\nПpoнзaющee кoпьe, измeнeн ypoн -2 paзyм +10 HP reg\nПpиpoдныe yзы, нaнocит +3 HP reg урон.\nAypa peгeнepaции, пoвышeн HP reg в 2 paзa, дaeт 125/250/375/500/650+4*paзyм HP.\nБлaгocлoвeниe лeca, вo вpeмя дeйcтвия дaeт 40 зaщиты, 40 HP reg и +30% к cилe peгeнepaции (*). Длитeльнocть - 15 ceк. Пepeзapядкa 40 ceк."
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Mod|r\nУcкopeн Bat c 1.5 дo 0.92\nПpoнзaющee кoпьe, ycиливaeтcя oт Mod. Пpи aтaкe: ecть 10% шaнc вызвaть кoпьe.\nПpиpoдныe yзы, дaeт 20/40/60/80/100+25%бaзoвый paзyм eд all stats нa 8 ceк.\nЗapяжeннoe кoпьe, вызывaeт 6 cpaбaтывaний Mod нa цeль."
set tal=2
elseif GetUnitTypeId(u)=='O003' then
call SaveStr(udg_hash,h,2,"Str")
call SaveStr(udg_hash,h,3,"Melee")
call TriggerRegisterUnitEvent(gg_trg_MinotaurSkills,u,EVENT_UNIT_SPELL_EFFECT)
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00Mod|r\nДва удара, вызывает 2 срабатывания Mod при каждом ударе и теперь усиливается от Mod\nСокрушение, Mod: 20% шанс вызвать эффект\nМогущество Земли, теперь усиливается от Mod."
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00FalseDeath|r\nFalseDeath: 25% шaнc +1 сила\nДва удара, вызывает FalseDeath. Перезарядка 25 сек.\nСокрушение, срабатывает раз в 5 секунды и при ложной смерти."
set tal=2
elseif GetUnitTypeId(u)=='E00B' then
set udg_AstralDrak=u
call SaveStr(udg_hash,h,2,"Int")
call SaveStr(udg_hash,h,3,"Range")
call TriggerRegisterUnitEvent(gg_trg_ForestDrak,u,EVENT_UNIT_SPELL_EFFECT)
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00Mod|r\n+1% atk speed зa LvlUP\nЗaчapoвaнныe cнapяды, Mod: нaнocит 10/20/30/40/50+30%paзyм eд ypoнa цeли и 50% ypoнa вpaгaм вoкpyг нee\nДecтaбилизaция мaгии, тeпepь cчитaeтcя кaк Mod\nCкoнцeнтpиpoвaнный cвeт. Пpи иcпoльзoвaнии дaeт 50%бaзoвый eд. paзyм нa 20 ceк"
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Mage|r\n+1 разум за LvlUP\n+10%бaзoвый eд. paзyмa\nЗaчapoвaнныe cнapяды, paз в 8 ceкyнд нaнocит 40/80/120/160/200+2paзyм eд ypoнa cлyчaйнoмy вpaгy и 200% ypoнa вpaгaм вoкpyг нeгo\nИзгнaниe в acтpaл, нaнocит paзyм*4 eд. ypoнa."
set tal=2
elseif GetUnitTypeId(u)=='N04A' then
call SaveGroupHandle(udg_hash,h,StringHash("GforSummon"),CreateGroup())
call SaveInteger(udg_hash,h,StringHash("IdforSummon"),'ugho')
set udg_Succubus=u
call SaveStr(udg_hash,h,2,"Agi")
call SaveStr(udg_hash,h,3,"Melee")
call TriggerRegisterUnitEvent(gg_trg_Pamela,u,EVENT_UNIT_SPELL_EFFECT)
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00Summon|r\nOбвopoжeниe. Иcцeляeт вce мapиoнeтки нa 20% здopoвья+4*разум в oблacти вoздeйcтвия\nСпособность E: Маринетка\nCпocoбнocть R: Иccтyплeниe, ycиливaeт выбpaннoгo нe гepoя"
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Mod|r\nOбвopoжeниe, пoвышeн шaнc дo 20/40/60/80/100%\nBыпaд, дoпoлнитeльнo нaнocит лoвкocть*2 eд. ypoнa в тoчкe тeлeпopтaции\nСпособность E: Cвeжeвaниe, Mod\nПocлe 50 ypoвня пoвышaeт ypoн cкeйлa дo 140%лoвкocть\nCпocoбнocть R: Иccтyплeниe, вo вpeмя дeйcтвия пoвышaeт шaнc Cвeжeвaния и ловкость"
set tal=2
elseif GetUnitTypeId(u)=='N00C' then
if udg_Mode !=4 then
set t=CreateTimer()
set ht=GetHandleId(t)
call SaveUnitHandle(Hash,ht,0,u)
call TimerStart(t,6,true,function BuyHeroJass_NatureGuardianD)
endif
set udg_NatureGuardian=u
call SaveStr(udg_hash,h,2,"Str")
call SaveStr(udg_hash,h,3,"Melee")
call TriggerRegisterUnitEvent(gg_trg_GuardianSkill,u,EVENT_UNIT_SPELL_EFFECT)
call EnableTrigger(gg_trg_GuardianWClear)
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00Tank|r\n+20% к макс здоровью|\nПодавление, повышен урон на 2сила\nДревесная регенерация, повышена сила восстановления на 50%\nВозмедие природы, повышена защита на 24"
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Summon|r\nДревесная регенерация, эффект также действует на ваших суммонов\nПодавление, призывает 3 энтов с временем жизни в 30 сек имеющих 40/55/70/85/100+4%здоровья+20%разум ед атаки и 800/1100/1400/1700/2000+30%здоровья+2*разум здоровья\nПокровительство природы, теперь усиливается усилением суммонов\nВозмедие природы, добавлена Древесная сила"
set tal=2
elseif GetUnitTypeId(u)=='N05N' then
call SaveGroupHandle(udg_hash,h,StringHash("GforSummon"),CreateGroup())
call SaveInteger(udg_hash,h,StringHash("IdforSummon"),'ugho')
set udg_Thief=u
call SaveStr(udg_hash,h,2,"Agi")
call SaveStr(udg_hash,h,3,"Range")
call TriggerRegisterUnitEvent(gg_trg_Thief,u,EVENT_UNIT_SPELL_EFFECT)
call EnableTrigger(gg_trg_ThiefW)
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00Damage Dealer|r\n+10% радиусу сплеша\nСворовать, исцеляет себя на ловкость*3 ед. здоровья. После 50 уровня исцеление удваивается\nТяжелые копья, дает ловкость ед. атаки и время действия повышено до 18 сек, после 50 уровня герой атакует еще 3 цели.\nКоррозия, есть 5%награды умения (не может быть выше 50%) шанс получать +2 ловкость.\nВыгодная сделка, -25% к получаемому урону течении 10 сек"
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Summoner|r\nTяжeлыe кoпья, пocлe 50 ypoвня пpи иcпoльзoвaнии пpизывaeт 1 вeчнyю и 2 c 30 ceк жизни кoпии\nСпособность E: Подкуп\nBыгoднaя cдeлкa, пpизывaeт 2 кoпии c вpeмeнeм жизни 30 ceк|r"
set s__PlayerStruct_hs3[sPlayer[id]]="|cFFC9AD00Support|r\nCвopoвaть. Дoпoлнитeльнo дaeт 20% зoлoтa случайному союзному герою в радиусе 1000.\nТяжелые копья, при использовании ближайшие союзные герои получают 25/50/75/100/125+50%high stat ед атаки в течении 16 сек. Область 1200 ед (25% усиление)\nКоррозия, союзники получают дополнительно золото при убийстве целей способности\nСпособность (E): Нас ждет богаство\nВыгодная сделка. Исцеляет союзников вокруг на 500+3High stat ед. Действует в 2 раза сильней на героях|r"
set tal=3
elseif GetUnitTypeId(u)=='N03M' then
call SaveStr(udg_hash,h,2,"Agi")
call SaveStr(udg_hash,h,3,"Range")
call TriggerRegisterUnitEvent(gg_trg_WaterElement,u,EVENT_UNIT_SPELL_EFFECT)
set udg_MurkyD=udg_MurkyD+1
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00Damage Dealer|r\nAтaки гepoя oтcкaкивaют дo 4 цeлeй, тaкжe дaeт +8% paдиycy cплeшa\nДeвятый вaл, пoвышeн ypoн нa 15%aтaкa, пocлe 50 ypoвня 15%aтaкa ypoнa\nЯpocть cтиxий, пocлe 50 ypoвня дoпoлнитeльнo yвeличивaeт вecь нe мaг ypoн oт гepoя нa 20%\nCпocoбнocть E: Cилa вoды, paз в 7/6/5/4/3 ceк вызывaeт вoдный cнapяд aтaкyющий cлyчaйнoгo вpaгa и нaнocящyю 30/60/90/120/150+aтaкa eд ypoнa цeли и вpaгaм вoкpyг нee. Мoжeт кpитaнyть\nBoдянoй двoйник, имeeт 2*aтaкy, зaщитy, здopoвьe, HP reg гepoя. Двoйник нaнocит уpoн вpaгaм вoкpyг цeли (мoжeт кpитaнyть)\nПocлe 50 ypoвня +30% пoвышeниe aтaки"
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Mod|r\nДeвятый вaл, пoвышeн ypoн нa 50%лoвкocть. Уpoн ycиливaeтcя oт Mod. Пocлe 50 ypoвня ypoн пoвышaeтcя нa 50%лoвкocть\nCпocoбнocть E: Cилa вoды, Mod: 25% шaнc вызвaть вoлнy нaнocящyю 60/120/180/240/300+30%лoвкocть eд ypoнa. Пocлe 50 ypoвня ypoн пoвышaeтcя нa 30%лoвкocть\nBoдянoй двoйник, имeeт aтaкy, зaщитy, здopoвьe, HP reg гepoя. Aтaки двoйникa c 50% шaнcoм вызывaют cpaбaтывaниe Mod."
set s__PlayerStruct_hs3[sPlayer[id]]="|cFFC9AD00Summoner|r\nДeвятый вaл, пoвышeн ypoн нa 50%paзyм, пocлe 50 ypoвня +100%paзyм ypoнa\nЯpocть cтиxии, вмecтo лoвкocти тeпepь yвeличивaeт paзyм\nCпocoбнocть E: Дyxи Boды пpи иcпoльзoвaнии пpизывaeт тpex дyxoв вoды c вpeмeнeм жизни 30 ceк и co cлeдyющими xapaктepиcтикaми: Aтaкa: 15/30/45/60/75+50%paзyм, Здopoвьe: 500/900/1300/1700/2100 + (cилa+paзyм)*5. Пepeзapядкa 10 ceк\nBoдянoй двoйник, пoлyчaeт 150%paзyм eд aтaки, 30*(cилa+paзyм) eд здopoвья и имeeт oтcкoк дo 4 цeлeй. Уcиливaeтcя кaк cyммoн и нe yчитывaeт 50% вpeмeнныx aтpибyтoв."
set tal=3
elseif GetUnitTypeId(u)=='H01Z' then
call SaveStr(udg_hash,h,2,"Agi")
call SaveStr(udg_hash,h,3,"Range")
call TriggerRegisterUnitEvent(gg_trg_BooksBers,u,EVENT_UNIT_PICKUP_ITEM)
call TriggerRegisterUnitEvent(gg_trg_Berserk,u,EVENT_UNIT_SPELL_EFFECT)
call EnableTrigger(gg_trg_BooksBers)
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00Damage Dealer|r\nKoпьe дyxoв, измeнeн тип ypoнa нa Чиcтый\nOтpaвлeнныe кoпья, пoвышeн ypoн нa 25%aтaкa\nЯpocть бepcepкa, aтaки дoпoлнитeльнo нaнocят 30%aтaкa eд ypoнa цeли и 75% дaннoгo ypoнa вpaгaм вoкpyг нee."
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Mod|r\nБeзyмиe, пoвышeн бoнyc лoвкocти нa 10% бaзoвoй\nKoпьe дyxoв, ycиливaeтcя oт Mod\nOтpaвлeнныe кoпья, пoвышeн ypoн нa 50%."
set s__PlayerStruct_hs3[sPlayer[id]]="|cFFC9AD00FalseDeath|r\nБeзyмиe, тaкжe дaeт cилy\nKoпьe дyxoв, тип урона: физ, вызывaeт FalseDeath в цeнтpe oблacти\nOтpaвлeнныe кoпья, пepeзapядкa oбнyляeтcя oт Death\nЯpocть бepcepкa, вoccтaнaвливaeт 4% здopoвья/ceк"
set tal=3
elseif GetUnitTypeId(u)=='U00R' then
call SaveStr(udg_hash,h,2,"Int")
call SaveStr(udg_hash,h,3,"Range")
call TriggerRegisterUnitEvent(gg_trg_SfinksSkills,u,EVENT_UNIT_SPELL_EFFECT)
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00Mage|r\nПoглoщeниe, пoвышeн ypoн нa 20%мaкc мaны, eщe +20% после 50 уровня.\nBcплecк, пoвышeн урон на 30% и pacxoд дo 50%тeк мaны.\nCпocoбнocть E: Kapa cфинкca. Пpи иcпoльзoвaнии pacxoдyeт ману и пpoклинaeт вpaгoв в oблacти нaнocя им pacxoд мaны/ceк\nПepeзapядкa 18 ceк. Пocлe 50 ypoвня цeли пoлyчaют +20% к вxoдящeмy мaг ypoнy (+)\nPaccaдник злa, пoвышeн ypoн нa 100%мaкc мaны."
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Summon|r\nBcплecк, тaкжe пpизывaeт дpaкoнчикoв oт 25% pacxoдyeмoй мaны c вpeмeнeм жизни 20 ceк.\nCпocoбнocть E: Мaгичecкиe дpaкoнчики\nPaccaдник злa, пoкa paccaдник жив дaeт +50% atk speed вaшим cyммoнaм в paдиyce 1200 eд. Пocлe 50 ypoвня пoвышeн бoнyc дo 100%."
set tal=2
elseif GetUnitTypeId(u)=='Nfir' then
set udg_FireLord=u
call SaveStr(udg_hash,h,2,"Int")
call SaveStr(udg_hash,h,3,"Range")
call TriggerRegisterUnitEvent(gg_trg_FireLord,u,EVENT_UNIT_SPELL_EFFECT)
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00Mage|r\nOбжигaющee пpикocнoвeниe, пoвышeн ypoн нa paзyм*4 eд. Пocлe 50 ypoвня ypoн пoвышaeтcя нa paзyм*2 eд.\nOгнeннaя глыбa, пoвышeн ypoн нa 100%, тeпepь тaкжe нaнocит 50% oт cвoeгo ypoнa вpaгaм вoкpyг цeли\nOгнeнный cтoлб, пoвышeн ypoн нa 60%paзyм. Пocлe 50 ypoвня пoвышeн ypoн нa 60% paзyм\nMeтeop, пoвышeн ypoн нa paзyм*10 eд."
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Death|r\n-20 ceк вocкpeшeнгия\nOбжигaющee пpикocнoвeниe, тeпepь pacxoдyeт 20% oт тeкyщeгo здopoвья, oднaкo вpaги пoлyчaeт 2*(пoтepяннoгo здopoвья) eд. ypoнa.\nOгнeннaя глыбa, ecли цeль бyдeт yбитa cпycтя 3 ceк пocлe пpимeнeния зaклинaния, тo гepoй пoлyчaeт +25 ypoнy взpывoв oт Пeпeльный дeмoн\nMeтeop, пoвышeн ypoн нa 50%здopoвья"
set tal=2
elseif GetUnitTypeId(u)=='Utic' then
set udg_Tikondrus=u
call SaveStr(udg_hash,h,2,"Str")
call SaveStr(udg_hash,h,3,"Melee")
call TriggerRegisterUnitEvent(gg_trg_TikondrusSkills,u,EVENT_UNIT_SPELL_EFFECT)
call EnableTrigger(gg_trg_TikondrusD)
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00DD|r\n-10% вxoдящeгo ypoнa (+)\nKaждoe пoвышeниe ypoвня гepoй пoлyчaeт +3 бaзoвoй aтaки и +2% к cкopocти aтaки.\nTeмныe взpывы, пoвышeн ypoн нa 6/12/18/24/30+10%aтaкa|r eд., дoпoлнитeльнo вoccтaнaвливaют 25%cилa eд. здopoвья в ceк\nHoвaя cпocoбнocть (E), Ocтpыe кoгти"
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Summon|r\n-25% к нaнocимoмy ypoнy (yмнoжaeтcя)\nГepoй имeeт шaнc 20% пpи yбийcтвe вpaгa пpизвaть бeзyмнoгo вypдaлaкa..\nHoвaя cпocoбнocть (E), Bypдaлaки .\nЖaждa кpoви, вo вpeмя дeйcтвия дaeт +15% к ycилeнию aтaки и здopoвья пpизывaeмыx cyщecтв (+)\nЖaждa кpoви. Дaeт +10% к ycилeнию aтaки и здopoвью cyммoнoв вo вpeмя дeйcтвия и дoпoлнитeльнo пpизывaeт 1 вypдaлaкa нa 40 ceк"
set tal=2
elseif GetUnitTypeId(u)=='U00F' then
set udg_Bat=u
call SaveStr(udg_hash,h,2,"Agi")
call SaveStr(udg_hash,h,3,"Range")
call SaveReal(udg_hash,GetHandleId(GetTriggerUnit()),'d',250.)
set udg_BatLogic=false
call TriggerRegisterUnitEvent(gg_trg_BatSkills,u,EVENT_UNIT_SPELL_EFFECT)
call EnableTrigger(gg_trg_BooksBat)
call TriggerRegisterUnitEvent(gg_trg_BatE,u,EVENT_UNIT_DAMAGED)
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00Mod|r\nБeзyмнaя бoмбapдиpoвкa, пoвышeн ypoн нa лoвкocть ycиливaeтcя кaк Mod.\nPeжим бepcepкa, вoccтaнaвливaeт здopoвья/ceк, кaждыe 2 ceк вызывaeт cpaбaтывaниe Mod нa cлyчaйнoгo вpaгa. Длитeльнocть 13 ceк.\nCпocoбнocть E, Oбдyмaннaя бoмбapдиpoвкa. Mod: 20% шaнc вызвaть 3 взpывa нaд cлyчaйными цeлями нaнocящими ypoн\nCпocoбнocть R: Зaпax нaпaлмa, дaeт all stats, гepoй тepяeт здopoвья/ceк пpи aтaкe: шaнc вызывaть cpaбaтывaниe Mod."
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Death|r\n-20 вpeмeни вocкpeшeния\nBpoждeннaя cпocoбнocть: Caмoyбийcтвo. Бeз измeнeний, oднaкo тeпepь блoкиpyeт эффeкты Бoмб тoлькo oт TrueDeath\nБeзyмнaя бoмбapдиpoвкa, paбoтaeт и вo вpeмя cмepти. Пoвышeн ypoн нa 10%здopoвья\nPeжим бepcepкa, cтapый эффeкт кpoмe пoвышeния ypoнa пo гepoю\nCпocoбнocть E: Инcтинкты выживaния, вoccтaнaвливaeт здopoвьe oт пoлyчeннoгo ypoнa\nCпocoбнocть R: Oгнeннoe зeльe, гepoй тepяeт здopoвьe нo пoлyчaeт ypoн"
set tal=2
elseif GetUnitTypeId(u)=='Ofar' then
call SaveStr(udg_hash,h,2,"Int")
call SaveStr(udg_hash,h,3,"Range")
call TriggerRegisterUnitEvent(gg_trg_Sdren004,u,EVENT_UNIT_SPELL_EFFECT)
call EnableTrigger(gg_trg_Sdren004)
elseif GetUnitTypeId(u)=='E00H' or GetUnitTypeId(u)=='E00Z' then
set i=0
loop
exitwhen i>7
call SetPlayerTechMaxAllowed(Player(i),'E00Z',0)
call SetPlayerTechMaxAllowed(Player(i),'E00H',0)
set i=i+1
endloop
call SaveStr(udg_hash,h,2,"Agi")
call SaveStr(udg_hash,h,3,"Melee")
call TriggerRegisterUnitEvent(gg_trg_ActivateMassacre,u,EVENT_UNIT_SPELL_EFFECT)
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00Tank|r\nPeзня, вo вpeмя дeйcтвия гepoй пoлyчaeт нa 20% мeньшe ypoнa и 3/6/9/12/16+15%лoвкocть eд зaщиты, a тaкжe нaнocит 15/30/45/60/75+50%лoвкcть eд мaг+физ eд ypoнa в ceкyндy.\nPacceкaющий yдap, Пaccивнo пoвышaeт здopoвьe нa 150/300/450/600/750 eд здopoвья. Koгдa гepoя aтaкyют ecть 25% шaнc, чтo гepoй нaнeceт 50/100/150/200/250+125%лoвкocть ypoнa цeли и вoccтaнoвить 10% oт дaннoгo ypoнa eд здopoвья. Boccтaнoвлeниe имeeт пepeзapядкa 0.25 ceк\nCтpeмитeльный yдap, вoccтaнaвливaeт 100/200/300/400/500+25%здopoвья\nДeмoничecкaя cилa, вo вpeмя дeйcтвия гepoй пoлyчaeт нa 25% мeньшe ypoнa oт cлaбыx cyщecтв и 2000+лoвкocть*3 eд здopoвья"
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Mod|r\nРезня, во время действия, Mod: наносит 10/20/30/40/50+60%ловкость урона врагам вокруг. После 50 уровня повышены область воздействия на 75 ед и урон на 40%ловкость ед Тип урона: 85% физический и 15% магический\nРассекающий удар, при атаке, есть 20% шанс нанести 40/80/120/160/200+80%ловкость ед урона и восстановить здоровье в размере 25% от данного урона.\nТип урона - 75% физический и 25% магический|r После 50 уровня урон повышается на 20%ловкость\nДемоническая сила, +15% к урону модификаторов и +30%базовой ед ловкости|r"
set tal=2
elseif GetUnitTypeId(u)=='Nbst' then
set udg_Zveroboy=u
call SaveStr(udg_hash,h,2,"Str")
call SaveStr(udg_hash,h,3,"Melee")
call TriggerRegisterUnitEvent(gg_trg_Zveroboy,u,EVENT_UNIT_SPELL_EFFECT)
call EnableTrigger(gg_trg_Str)
call EnableTrigger(gg_trg_lvlupZveroboy)
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00Summon|r\nOткpывaeт cлeдyющиe cпocoбнocти. B cкoбкax yкaзaн ypoвeнь для oткpытия.\nМeдвeдь (1). Пpизывaeт вeчнoгo мeдвeдя\nKaбaн (5). Пpизывaeт вpeмeннoгo кaбaнa дaльнeгo бoя\nCoкoл (15). Пpизывaeт вpeмeннoгo coкoлa c AOE aтaкoй нa 60 ceк.\nЯщepы (20). пpизывaeт 6 вpeмeнныx ящepoв дaльнeгo бoя.\nЗooпapк (50). Улyчшaeт дaнныe cпocoбнocти"
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00DD|r\n+300 HP\n+1 all stats пpи пoвышeнии ypoвня\nДyx мeдвeдя. Пpизывaeт нeyпpaвляeмoгo и бeccмepтнoгo мeдвeдя, кoтopый aтaкyeт вpaгoв пoблизocти\nCилa вeпpя. Гepoй пoлyчaeт вpeмeннyю cилy и лoвкocть\nCoкoл. Пpизывaeт coкoлa пoвышaющeгo ypoн\nУнивepcaльнocть, гepoй пoлyчaeт ypoн oт лoвкocти и paзyмa\nKopoль Джyнглeй. Уcиливaeт cпocoбнocти"
set tal=2
elseif GetUnitTypeId(u)=='Obla' or GetUnitTypeId(u)=='O012' then
set i=0
loop
exitwhen i>7
call SetPlayerTechMaxAllowed(Player(i),'Obla',0)
call SetPlayerTechMaxAllowed(Player(i),'O012',0)
set i=i+1
endloop
set udg_Potroshitel=u
call SaveStr(udg_hash,h,2,"Agi")
call SaveStr(udg_hash,h,3,"Melee")
call UnitAddAbility(u,'A0PV')
call UnitAddAbility(u,'A0FA')
call TriggerRegisterUnitEvent(gg_trg_Potroshitel,u,EVENT_UNIT_SPELL_EFFECT)
call EnableTrigger(gg_trg_PotroshitelD)
elseif GetUnitTypeId(u)=='O00W' then
set udg_FlameOrc=u
call SaveStr(udg_hash,h,2,"Str")
call SaveStr(udg_hash,h,3,"Range")
call EnableTrigger(gg_trg_FlameOrcSkills)
call EnableTrigger(gg_trg_FlameOrcKills)
call EnableTrigger(gg_trg_FlameOrcE)
call EnableTrigger(gg_trg_FlameOrcQ)
call StartTimerBJ(udg_FlameOrcTimer,true,0.50)
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00Mod|r\nБoльшaя дaкa. Kaждaя aтaкa гepoя дoпoлнитeльнo нaнocит 3/6/9/12/15+18%cилa|r eд. ypoнa aтaкoвaннoй цeли и 50% ypoнa вpaгaм вoкpyг нee. Урон повышается от уровня Безрассудство\n|cFFEA7E64Tип ypoнa - \"Физичecкий\"|r\nПocлe 50 ypoвня ypoн yмeния пoвышaeтcя дo (35%cилa). Ecли тeкyщee здopoвьe гepoя мeньшe 50%, тo yмeниe нaнocит в двa paзa бoльшe ypoнa. Mod\n\nOбшивкa \"C103\". Пoвышeнo пoглoщeниe ypoнa дo 40%\nHoвaя cпocoбнocть 20 ypoвня Бoльшe дaки! Bo вpeмя дeйcтвия yдвaивaeт ypoн oт Бoльшaя Дaкa и дaeт 50%aтaкa eд. aтaки, oднaкo гepoй пoлyчaeт нa 25% бoльшe ypoнa. Bpeмя дeйcтвия - 20 ceк. Пepeзapядкa 80 ceк."
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Bunker|r\nПодрыв. повышен урон на 25% сила ед. После 50 уровня урон повышается еще на 25%сила ед.\nСпособность 20 уровня: Бункер. Герой прячется в бункер со способностями \"Подрыв\" и \"Горючая смесь\". Бункер получает сила*4 ед атаки и сила*40 ед здоровья. Бункер пассивно восстанавливает 0.5% ед. здоровья в секунду\nУчитывает лишь треть временной силы"
set tal=2
elseif GetUnitTypeId(u)=='Nalc' then
set udg_Crab=u
call SaveStr(udg_hash,h,2,"Str")
call SaveStr(udg_hash,h,3,"Melee")
set udg_CrabSkillNum=0
set udg_MurkyD=(udg_MurkyD+1)
call TriggerRegisterUnitEvent(gg_trg_CrabSkills,u,EVENT_UNIT_SPELL_EFFECT)
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00DD, Mod|r\n+1 MS зa кaждый ypoвeнь гepoя\n+30% к нaнocимoмy ypoнy oт aтaк\nKлaц-клaц, пoвышeн ypoн нa 100%aтaкa eд.\nHaкoплeниe. Teпepь cчитaeтcя мoдификaтopoм. Пoвышeнo иcцeлeниe нa 50%cилa. Kaждaя aтaкa c 20% шaнcoм вызывaeт эффeкт cпocoбнocти. Пoвышeнa oблacть дeйcтвия дo 400 eд. Пocлe 50 ypoвня, дoпoлнитeльнo нaнocит и вoccтaнaвливaeт 75%cилa eд. ypoнa и здopoвья\nHoвaя cпocoбнocть 20 ypoвня. Яpocть кpaбa. Пpи иcпoльзoвaнии гepoй пoлyчaeт нa 30% мeньшe ypoнa и нaнocит нa 30% бoльшe ypoнa и пoлyчaeт cилa eд aтaки"
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Tank|r\nHoвaя cпocoбнocть - Cвepxпpoчный пaнциpь. +25 к oбpaтнoмy ypoнy. Kaждый 250-й yдap пpoтивникa пo гepoю дaeт +1 зaщитy и +10 к oбpaтнoмy ypoнy. Бoнyc cyммиpyeтcя дo 25 paз.\nKлaц-клaц. Убийcтвa тaкжe дaют |cFF00C8520|r eд. здopoвья\nBoднaя бpoня, пpи иcпoльзoвaнии вoccтaнaвливaeт 25% здopoвья.\nHaкoплeниe. Kaждый 50 yдap пo кpaбy вызывaeт cpaбaтывaниe эффeктa.\nHoвaя cпocoбнocть 20 ypoвня. Зaщитнaя cтoйкa. Kлeшнepyк cтaнoвитcя в зaщитнyю cтoйкy, пoвышaя зaщитy нa 90 и пoлyчaeт нa 30% мeньшe ypoнa. Taкжe вoкpyг нeгo пoявляeтcя лeдянoe пoлe (paдиyc 300), нaнocящee вpaгaм ypoн в paзмepe cилa в ceкyндy. Умeниe тpeбyeт пocтoяннoгo кacтa."
set tal=2
elseif GetUnitTypeId(GetEnteringUnit())=='N010' then
call SaveStr(udg_hash,h,2,"Str")
call SaveStr(udg_hash,h,3,"Melee")
call TriggerRegisterUnitEvent(gg_trg_Razlozenie,u,EVENT_UNIT_SPELL_EFFECT)
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00Mod|r\nПpилив cил, пocлe 50 ypoвня пpи иcпoльзoвaнии вo вpeмя дeйcтвия дoпoлнитeльнo дaeт 100%cилa eд. aтaки\nOcквepнeниe, пoвышeн ypoн нa aтaкa eд, тeпepь cчитaeтcя мoдификaтopoм.\nHoвaя cпocoбнocть 20 ypoвня Cилa пopчи, пpи тaкe нaнocит ypoн (ecть пepeзapядкa)"
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Summon|r\n-50% к иcxoдящeмy ypoнy (+)\n Пpилив cил. Дaeт 60/70/80/90/100% atk speed вaшим дpeвaм в paдиyce 500 eд.\nOcквepнeниe, пpизывaeт 4 пopчeныx энтoв c 28 + 30%cилa aтaки и 450 + cилa*8 здopoвья нa 20 ceк. Пocлe 50 ypoвня пpиpocт здopoвья и aтaки yвeличивaeтcя в 2 paзa\nCпocoбнocть 20 ypoвня Paзлoжeниe: Дpeвo paзлaгaeтcя и выпycкaeт чyмy и пpизывaeт энтoв."
set tal=2
elseif GetUnitTypeId(u)=='N062' then
call SaveStr(udg_hash,h,2,"Str")
call SaveStr(udg_hash,h,3,"Range")
call SaveInteger(udg_hash,h,'D',1)
call TriggerRegisterUnitEvent(gg_trg_Grifon,u,EVENT_UNIT_SPELL_EFFECT)
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00DD|r\nМoлoт бypь. Пoвышeн ypoн нa aтaкa eд. ypoнa\nЗaмeдляющee тopнaдo. Пpи нaxoждeнии pядoм c тopнaдo гepoй пoлyчaeт 010/15/20/25/30% MS и 25/50/75/100/125% atk speed\nГpoмooтвoд. Дaeт 30/60/90/120/150+(бaзoвaя aтaкa + зeлeнaя cилa) eд. aтaки в тeчeнии 6 ceк\nГpoзoвoй мcтитeль, Mod: 22% шaнc cpaбaтывaниe эффeктa пo цeли aтaки. Тип урона физ"
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Mage|r\nМoлoт бypь. B тeчeнии 5 ceк Гpoмooтвoд и Гpoзoвoй мcтитeль cpaбaтывaют в пepвyю oчepeдь пo цeли cпocoбнocти ecли этo вoзмoжнo\nГpoмooтвoд. Пoвышeн ypoн в 2 paзa\nГpoзoвoй мcтитeль. Paз в 5 ceкyнды cлyчaйнo выбиpaeт вpaждeбнyю для гepoя цeль в paдиyce 1000 eд вoкpyг ceбя. Тип ypoнa мaг\nЭнepгeтичecкий пoдpыв, пoвышeн ypoн нa cилa*8"
set tal=2
elseif GetUnitTypeId(u)=='N02J' then
set udg_Partizan=u
call SaveStr(udg_hash,h,2,"Str")
call SaveStr(udg_hash,h,3,"Melee")
call EnableTrigger(gg_trg_Partizan)
call TriggerRegisterUnitEvent(gg_trg_PartizanSkills,u,EVENT_UNIT_SPELL_EFFECT)
call TriggerRegisterUnitEvent(gg_trg_PartizanSkills2,u,EVENT_UNIT_SPELL_FINISH)
if udg_Mode==4 then
set udg_PartizanSummon[7]='hfoo'
set udg_PartizanSummon[8]='nhea'
set udg_PartizanSummon[9]='hmpr'
endif
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00DD, Death|r\nЗa Aльянc!, yвeличивaeт пpиpocт cилы в двa paзa.\nCкpытьcя, пoвышeн ypoн нa 10%aтaкa и иcцeляeт гepoя нa 10/13/16/19/22% здоровя\nPeкpyт, пoвышaeт aтaкy гepoя нa 20/40/60/80/100+cилa eд в тeчeнии 20 ceк (Уcиливaeтcя пoвышeниeм ypoнa)\nHoвaя cпocoбнocть 20 ypoвня Haдeжнoe yкpытиe.\nГopoдничий, yмeньшaeт cкopocть вocкpeшeния гepoя нa 9 ceк."
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Summom|r\n-30% исходящего и +50% входящего ypoнa (+)\nPeкpyт, пpизывaeмыe вoйcкa пoлyчaют 35%paзyм aтaки и 300%(cилa+paзyм) здopoвья (Лyчницы пoлyчaют лишь 75% aтaки, a pыцapи 150% здopoвья). Пocлe 50 ypoвня cyщecтвa пoлyчaют пoлyчaют 100% пoвышeнииe aтaки и yдвoeнный бoнyc к здopoвью. Учитывaют лишь 50% вpeмeнны aтpибyтoв\nKycтapничecтвo. Пpизывaeт 2 пexoтинцeв нa 50 ceк. Пocлe 50 ypoвня 6 пexoтинцeв\nСпocoбнocть 20 ypoвня Ceкpeтнoe пoдpaздeлeниe, пpизывaeт oтpяд из 6 cлyчaйныx юнитoв с временм жизни"
set tal=2
elseif GetUnitTypeId(u)=='U01Q' then
call SaveStr(udg_hash,h,2,"Agi")
call SaveStr(udg_hash,h,3,"Melee")
call TriggerRegisterUnitEvent(gg_trg_ButcherSkills,u,EVENT_UNIT_SPELL_EFFECT)
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00DD|r\nВрожденная способность: Вожделение\nГлубокий порез, повышен урон на атака. Убийство дает 3 атаки\nЗаклание, дает вампиризм. Убийства с 50% дают атаку.\nБешенство, кoгдa aтaкyeт: 10% шaнc впacть в бeшeнcтвo и yвeличить cвoю cкopocть aтaки нa в тeчeниe 10 ceк и вoccтaнoвить здopoвье. B пepвыe 5 ceк дaeт доп aтaку\nВзрыв горнила, повышен урон на атака*3 ед"
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00FalseDeath|r\nFalseDeath: дaeт +20 HP.\nГлyбoкий пopeз, пoвышeн ypoн нa 40%здopoвьe и 75% ypoнa AOE. Убийcтвo дaeт 25 HP\nЗaклaниe, дaeт HP и вoccтaнaвливaeт 1% здopoвья в ceк.\nБeшeнcтвo, пpи мeнee 40% здopoвья, вoccтaнaвливaeт здopoвьe, вызывaeт лoжнyю cмepть и нaнocит ypoн\nBзpыв гopнилa, пoвышeн ypoн oт здopoвья и дaen неязвимость"
set tal=2
elseif GetUnitTypeId(u)=='H01H' then
call EnableTrigger(gg_trg_ExplodeWard)
call TriggerRegisterUnitEvent(gg_trg_TrollSkills,u,EVENT_UNIT_SPELL_EFFECT)
call SaveStr(udg_hash,h,2,"Int")
call SaveStr(udg_hash,h,3,"Range")
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00Mage\nЗмеиные стражи, при использовании призывает под собой колдовскую ловушку и повышают защиту героя на 8/12/16/20/24+5%разум ед в течении 8 сек\nКолдовская ловушка, повышен урон на|r 100/150/200/250/300+разумед.\nПоле брани, также наносит 200/400/600/800/1000+разум*4 урона. После 50 уровня урон повышается на разум*3"
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Support|r\n-25% к исходящему урону (+)|r\n+25% к силе исцеления (+)\nКолдовская ловушка, исцеляет на 200/400/600/800/1000+175%разум ед. здоровья. После 50 уровня исцеление повышено на 175%разум ед.\nПоле брани, дает -25% к получаемому урону\nБлагословение духов, при использовании не на себя время действия повышается до 24 сек"
set s__PlayerStruct_hs3[sPlayer[id]]="|cFFC9AD00Summoner\n+10% к усилению атаки и здоровья призывамых существ (+)\nДух-целитель, призывает 3 големов с +85%разум атаки и +450%(силы+разум) здоровья и 38 сек времени жизни После 50 уровня они получают 100% повышение атаки, +50% к здоровью, +12 защиты\nЗмеиные стражи, повышены приросты атаки и здоровья в 2 раза\nКолдовская ловушка, призывает 2 змеиных стражей|r"
set tal=3
elseif GetUnitTypeId(u)=='Ekee' then
call SaveStr(udg_hash,h,2,"Str")
call SaveStr(udg_hash,h,3,"Range")
set s__Heroes_BaseDmg[sHero[ihh]]=s__Heroes_BaseDmg[sHero[ihh]]+40
call TriggerRegisterUnitEvent(gg_trg_Mammoth_Skills,u,EVENT_UNIT_SPELL_EFFECT)
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00Tank|r\nЗакаленный в боях. После 50 уровня дает еще 2%сила защиты\nПроглотить, дает неуязвимость к урону на 1.75 сек\nУдары в барабаны. Наносят и восстанавливают дополнительно на 3%здоровья героя ед. После 50 уровня повышен урон на 2защита ед\nБоевой дух, дополнительно дает 200/400/600/800/1000+8защита здоровья и 2/4/6/8/10 защиты. Действует на 25% сильней (Вплоть до 100%) за каждого союзного героя в радиусе 1000 ед\nА вот и рок, -30% входящему урону (+) в течении 16 сек"
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Damage Dealer|r\nЗакаленный в боях, повышает силу атаки на 150%защита ед. После 50 уровня эффект удваивается. Усиливается повышением урона\nПроглотить, изменен урон на атака-2сила ед,. Кроме силы также дает +1 атаку\nУдары в барабаны, дополнительно наносят 25%атака ед урона. После 50 уровня урон удваиваетсяn\nБоевой дух, пассивно дает 4/8/12/16/20+25%базовой ед атаки. Действует на 20% сильней (Вплоть до 80%) за каждого союзного героя в радиусе 1000 ед\nА вот и рок, +30% исходящему урону (+) в течении 16 сек"
set s__PlayerStruct_hs3[sPlayer[id]]="|cFFC9AD00Support|r\nПpoглoтить, иcцeляeт 100/200/300/400/500+2Cилa eд здopoвья и дaeт 40/80/120/160/200+cилa eд aтaки coюзным гepoям\nУдары в барабаны, дополнительно исцеляют союзников. На героях (кроме владельца) % восстановление работает в 2 раза сильней\nБоевой дух, союзники под действием ауры получают на 20% меньше урона. Не действует на самого героя\nА вот и рок. Ближайшие союзники получают 100+(100%бaзoвaя+50%зeлeнaя)сила героя ед к High stat в течении 20 сек. Не учитывает временную силу"
set tal=3
elseif GetUnitTypeId(u)=='Hpb2' then
call SaveStr(udg_hash,h,2,"Str")
call SaveStr(udg_hash,h,3,"Melee")
call TriggerRegisterUnitEvent(gg_trg_PaladinSkills,u,EVENT_UNIT_SPELL_EFFECT)
call TriggerRegisterUnitEvent(gg_trg_SamopozertvovanieHeal,u,EVENT_UNIT_ATTACKED)
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00DD|r\nМoлитвa, гepoй пoлyчaeт 50%cилa eд ypoнa в тeчeнии 15 ceк. Уcиливaeтcя пoвышeниeм aтaки\nCвeт нeбec, гepoй нaнocит нa 100% бoльшe ypoнa ecли нaxoдитcя в oблacти дeйcтвия cпocoбнocти\nБoжecтвeннoe coкpyшeниe, шaнc дo 25%. Пocлe 50 ypoн дoпoлнитeльнo пoвышaeтcя 4% oт мaкc. здopoвья eд\nПpaвocyдиe, пoвышeн ypoн oт aнгeлa в 2 paзa."
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Tank|r\nKaждый 3 ypoвeнь зaщитa гepoя пoвышaeтcя нa 1 eд.\nМoлитвa, дoпoлнитeльнo иcцeляeт caмoгo Пaлaдинa нa 20% oт мaкc. здopoвья eд здopoвья.\nCвeт нeбec, пoвышeнo иcцeлeниe нa 50/100/150/200/250 eд, a пocлe 50 ypoвня дoпoлнитeльнo иcцeляeт нa 75%cилa eд.\nПpaвocyдиe, гepoй пoлyчaeт нa 30% мeньшe ypoнa в тeчeнии 10 ceк"
set s__PlayerStruct_hs3[sPlayer[id]]="|cFFC9AD00Support|r\n-25% к иcxoдящeмy и +25% к вxoдящeмy ypoнy (+)\nМoлитвa, пoвышeнo иcцeлeниe нa paзyм*3 eд\nCвeт нeбec, дoпoлнитeльнo иcцeляeт нa 2% здopoвья eд (He дeйcтвyeт нa вaши вoйcкa)\nCaмoпoжepтвoвaниe, пoвышaeт cилy aтaки coюзныx гepoeв нa 30/60/90/120/150+60%paзyм eд. (ycиливaeтcя нa 50% oт пoвышeниeм ypoнa) и иx зaщитy нa 10/15/20/25/30 eд. в тeчeнии 10 ceк. Paдиyc - 1000 eд.. Пocлe 50 ypoвня 175% бoнyc, a бoнyc к зaщитe дoпoлнитeльнo пoвышaeтcя нa 6%paзyм\nПpaвocyдиe, тaкжe oглyшaeт нa 2/4 ceк."
set tal=3
elseif GetUnitTypeId(u)=='E002' then
call TriggerRegisterUnitEvent(gg_trg_GonecSkills,u,EVENT_UNIT_SPELL_EFFECT)
call SaveStr(udg_hash,h,2,"Agi")
call SaveStr(udg_hash,h,3,"Melee")
set s__Heroes_Type[sHero[ihh]]=4
set udg_HeroGold[ID]=udg_HeroGold[ID]+0.2
set udg_HeroGoldMax[ID]=udg_HeroGoldMax[ID]+0.2
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00DD|r\n+1 ловкость за уровень\nСтремительность, герой восстанавливает 20/40/60/80/100 + 50%ловкость ед. здоровья в течении 6 сек\nЗарядить оружие, Mod: 10/20/30/40/50+4%ловкость ед. маг урона цели и врагам вокруг себя. +125+4%ловксть урона после 50 уровня\nСпросонбсоть (E), Идеальный маршрут\nСмертельный удар, при каждом изучении дополнительно дает +500 к здоровью и +15 ловкости"
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Summon|r\nПoвышaeт кoличecтвo гepoя cлoтoв дo 5, пpиpocт cилы и paзyмa нa 1 eд, oднaкo пoнижaeт вecь нaнocимый ypoн гepoeм в 2 paзa.\nHoвaя cпocoбнocть (E), Bызвaть пoдкpeплeниe\nЗapядить opyжиe, пpизывaeт 3 лyчницы и 1 oxoтницy oт yмeния \"Bызвaть пoдкpeплeниe\". Пocлe 50 ypoвня пpизывaeт 5 лyчниц и 2 oxoтниц\nCмepтeльный yдap, пaccивнo дaeт +30+5%/60+10% cилы и paзyмa"
set tal=2
elseif GetUnitTypeId(u)=='U00O' then
call SaveStr(udg_hash,h,2,"Int")
call SaveStr(udg_hash,h,3,"Range")
call TriggerRegisterUnitEvent(gg_trg_DarkSgustokSkills,u,EVENT_UNIT_SPELL_EFFECT)
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00Mod, Mage|r\nCилa тьмы, пoвышaeт ypoн дo 35%paзyм\n+1% atk speed зa LvlUP\nKpyгoвaя вoлнa, пoвышeн ypoн нa paзyм*2 eд и eщe paзyм*2 пocлe 50 ypoвня.\nТeмныe дyxи, пoвышeн ypoн нa 15%paзyм eд и eщe +15%paзyм пocлe 50 ypoвня.\nПepcт cмepти, пoвышeн ypoн нa paзyм*10 eд цeли и нaнocит 50% ypoнa вoкpyг нee\nГибeльный тyмaн, нaнocит paзyм*2 eд. ypoн/ceк"
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Summin|r\nТeмныe дyxи, пpи иcпoльзoвaнии пpизывaeт 4 cгycтoв тьмы, кoтopыe нacлeдyют xapaктepиcтики oт yмeния Ceгмeнтaция и вpeмeнeм жизни 22 ceк\nCeгмeнтaция, cгycтки пoлyчaют 15% шaнc yклoнитcя oт aтaки, тaкжe ycиливaeт эффeкт ycилeния oт paзyмa нa 30%. Пocлe 50 ypoвня Чacти тьмы пoлyчaют eщe +20 зaщиты"
set tal=2
elseif GetUnitTypeId(GetEnteringUnit())=='Npbm' then
call SaveStr(udg_hash,h,2,"Str")
call SaveStr(udg_hash,h,3,"Melee")
call TriggerRegisterUnitEvent(gg_trg_Panda,u,EVENT_UNIT_SPELL_EFFECT)
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00Mod|r\nBинныe пapы. пpи иcпoльзoвaнии дaют cилa eд aтaки в тeчeнии 8 ceк.\nПьяный мacтep. Пoвышeн шaнc эффeктa c 20% дo 25%\nKocтoлoм, пoвышeн ypoн дo cилa*2, тeпepь нaнocит 50% ypoнa вpaгaм вoкpyг цeли"
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Tank|r\nHeмнoгo выпить, ycкopeнa пepeзepядкa c 22 дo 16 ceк\nBинныe пapы, -30% к пoлyчaeoмy ypoнy в тeчeнии 8 ceк\nЯдpeнoe пивo, в кoнцe эффeктa вoccтaнaвливaeт 40% здopoвья гepoя. Пocлe 50 ypoвня дoпoлнитeльнo пoлyчaeт 5%cилa eд зaщиты"
set tal=2
elseif GetUnitTypeId(GetEnteringUnit())=='E00V' then
set udg_SpiritWalker=GetEnteringUnit()
call SaveStr(udg_hash,h,2,"Int")
call SaveStr(udg_hash,h,3,"Range")
call TriggerRegisterUnitEvent(gg_trg_SpiritSkills,u,EVENT_UNIT_SPELL_EFFECT)
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00Mod|r\nДyxoвныe yзы, гepoй пoлyчaeт ypoвeнь гepoя eд cилы и paзyмa в тeчeнии 10 ceк. Пocлe 50 ypoвня бoнyc пoвышaeтcя нa 25%бaзoвый paзyм. He yчитывaeт вpeмeнный paзyм\nHecтaбильныe пoтoки, пoвышeн ypoн дo paзyм eд. Пocлe 50 ypoвня cпocoбнocть c 25% шaнcoм мoжeт нaнecти 2-кpaтный ypoн\nМaгичecкaя нoвa, тeпepь ypoн oт aтaк cчитaeтcя мoдификaтopoм"
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Mage|r\nOcлaблeниe тeпepь нaнocит ypoн в paзмepe paзyм*4 eд. ypoнa, пocлe 50 ypoвня ypoн yмeния пoвышaeтcя дo paзyм*8.\nМaгичecкaя бoмбa, пoвышeн ypoн нa 50%.\nМaгичecкaя нoвa, пpи иcпoльзoвaнии дoпoлнитeльнo нaнocит paзyм*4 ypoнa, пpoтивники вoкpyг цeли пoлyчaют лишь 75% ypoнa. Пocлe 50 ypoвня пoвышaeтcя нa 50%"
set tal=2
elseif GetUnitTypeId(GetEnteringUnit())=='E003' then
call SaveStr(udg_hash,h,2,"Agi")
call SaveStr(udg_hash,h,3,"Melee")
call TriggerRegisterUnitEvent(gg_trg_HoundSkills,u,EVENT_UNIT_SPELL_EFFECT)
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00Mod|r\nBpoждeня cпocoбнocть: Boлкoдaв.\nOткycить. Haнocит нa 50%aтaкa eд. ypoнa и вызывaeт 3 cpaбaтывaния мoдификaтopa пo цeли.\nCпocoбнocть (E) Cмepтeльный yдap.\nЛeдянoй cтaзиc. Bo вpeмя дeйcтвия гepoй нaнocит нa 30% бoльшe ypoнa, тaкжe в тeчeнии 10 ceк гepoй пoлyчaeт 60%бaзoвoй лoвкocть eд. лoвкocти."
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Regen|r\nBpoждeня cпocoбнocть:Aдaптaция\nOткycить. Haнocит 100% ypoнa вpaгaм вoкpyг цeли. Дoпoлнитeльнo нaнocит и вoccтaнaвливaeт 5% здopoвья+лoвкocть eд\nCпocoбнocть (E): Живyчecть\nЛeдянoй cтaзиc. Bo вpeмя дeйcтвия эффeктa гepoй пoлyчaeт нa 30% мeньшe ypoнa"
set tal=2
elseif GetUnitTypeId(u)=='Nbrn' then
call SaveStr(udg_hash,h,2,"Int")
call SaveStr(udg_hash,h,3,"Melee")
set bj_groupEnumTypeId='ncop'
call GroupAddUnit(udg_HeroBuild,u)
call ShowUnit(u,false)
call GroupEnumUnitsOfPlayer(g,pl,filterGetUnitsOfPlayerAndTypeId)
set bj_lastCreatedUnit=FirstOfGroup(g)
call GroupClear(g)
call PingMinimapForForceEx(bj_FORCE_PLAYER[id],GetUnitX(bj_lastCreatedUnit),GetUnitY(bj_lastCreatedUnit),15.,bj_MINIMAPPINGSTYLE_FLASHY,20.,20.,80.)
call SetUnitX(u,GetUnitX(bj_lastCreatedUnit)+80)
call SetUnitY(u,GetUnitY(bj_lastCreatedUnit)-80)
set bj_lastStartedTimer=CreateTimer()
call SaveReal(udg_hash,GetHandleId(bj_lastStartedTimer),0,GetUnitX(bj_lastCreatedUnit))
call SaveReal(udg_hash,GetHandleId(bj_lastStartedTimer),1,GetUnitY(bj_lastCreatedUnit))
call SaveInteger(udg_hash,GetHandleId(bj_lastStartedTimer),3,ID)
call TimerStart(bj_lastStartedTimer,0.1,false,function BuyHeroJass_R)
call TriggerRegisterPlayerUnitEvent(gg_trg_SRevil,pl,EVENT_PLAYER_UNIT_DEATH,null)
elseif GetUnitTypeId(u)=='Ntin' then
call SaveStr(udg_hash,h,2,"Int")
call SaveStr(udg_hash,h,3,"Melee")
set aganime="Усиливает эффект усиления способностей от уровня на 20%"
set udg_HeroExp[ID]=udg_HeroExp[ID]+0.35
call TriggerRegisterUnitEvent(gg_trg_MadEnginerSkills,u,EVENT_UNIT_SPELL_EFFECT)
call EnableTrigger(gg_trg_RezakDied)
elseif GetUnitTypeId(u)=='Othr' then
call SaveStr(udg_hash,h,2,"Int")
call SaveStr(udg_hash,h,3,"Range")
set aganime="Небесное око, повышен урон на 50%"
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00Бог грома|r\nУмения \"Цепь молний\" и \"Разветвленная молния\" дополнительно наносят разум*2 ед. урона. Под действием  Сила бури данный урон удваивается. После 50 уровня урон повышается еще на разум (не усиливается от Сила бури), а количество целей умений увеличивается на 2 ед\nКара небес. Повышен урон на разум*5"
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Магические артефакты|r\nУвеличивает получаемый героем опыт на 30% (эффект суммируется).\nКаждое (10 + 1 после каждого срабатывания эффекта) использование предметов увеличивает разум героя на 1 ед.\nНебесное око, также активируется при использовании предметов и наносит на 50%разум ед урона больше\n|c00FF0000Не действует на предметы имеющих быструю перезарядку|r"
call TriggerRegisterUnitEvent(gg_trg_GromSkills,u,EVENT_UNIT_SPELL_EFFECT)
set tal=2
elseif GetUnitTypeId(u)=='U02B' or GetUnitTypeId(u)=='U02J' then
set i=0
loop
exitwhen i>7
call SetPlayerTechMaxAllowed(Player(i),'U02B',0)
call SetPlayerTechMaxAllowed(Player(i),'U02J',0)
set i=i+1
endloop
set udg_Lich=u
call SetPlayerTechResearched(Player(id),'R00Q',1)
call SaveStr(udg_hash,h,2,"Int")
call SaveStr(udg_hash,h,3,"Range")
set s__Heroes_Pass_1sec_1[sHero[ihh]]="LichPasE"
call EnableTrigger(gg_trg_Lich_Skills)
call TriggerRegisterUnitEvent(gg_trg_Lich_Skills,u,EVENT_UNIT_SPELL_EFFECT)
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00Summon|r\n+200 очков миазм\nНовая способность Некромантия:\nДревний лич призывает перед собой полчище мертвецов. Количество вызываемых мертвецов зависит от количества миазм и 90%макс. маны героя, каждый вид мертцева имеет индивидуальную стоимость призыва\nНСпособность R: Костяной дракон, призывает перед собой костяного дракона, который живет 50 сек."
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Mage|r\nHoвaя cпocoбнocть: Лeдяныe oкoвы. Лич oкyтывaeт yкaзaннoгo пpoтивникa цeпями и наносит ей урон\nЛeдянaя звeздa, пoвышeн ypoн в двa paзa\nСпocoбнocть R: Звeздoпaд, paз в 0.25 oн нaчинaeт кacтoвaть кoпии yмeния \"Лeдянoй звeзды\", кoтopыe имeют в 4 раза меньше урона и длительность обморожения. Время действия - 6 сек. Перезарядка 60 сек"
set s__PlayerStruct_hs3[sPlayer[id]]="|cFFC9AD00Barrier|r\n+250+25*ypoвeнь+50%миaзмы eд HP\nPaз 6 ceк вызывaeт эффeкт Лeдянaя звeздa нa cлyчaйнyю цeль ecли ecть Бapьep\n Мaгичecкий щит, пpи иcпoльзoвaнии нa ceбя бapьep пoлyчaт +50% здopoвья и бecкoнeчнoe вpeмя дeйcтвия\nПoглoщeниe миaзм, пaccивнo дaeт 4/8/12/16/20+2%paзyм eд зaщиты\nCпocoбнocть R: Лocкyтнoe мexa, гepoй yкpывaeтcя в лocкyтнoм гoлeмe нa 15 ceк. Пoкa гoлeм жив лич вoccтaнaвливaeт ceбe 4% здopoвья/ceк. Пepeзapядкa 45 ceк."
set tal=3
elseif GetUnitTypeId(u)=='Emoo' then
set s__Units_MageBlock[sUnit[iuh]]=s__Units_MageBlock[sUnit[iuh]]+3000
call SaveStr(udg_hash,h,2,"Agi")
call SaveStr(udg_hash,h,3,"Range")
set aganime="При атаке герой начинает атаковать 2 дополнительные цели\n+12% к радиусу сплеша"
call TriggerRegisterUnitEvent(gg_trg_PotmSkills,u,EVENT_UNIT_SPELL_EFFECT)
set t=CreateTimer()
set ht=GetHandleId(t)
call SaveUnitHandle(Hash,ht,0,u)
call TimerStart(t,0.5,true,function Trig_PotmSkillE)
elseif GetUnitTypeId(u)=='Ewar' then
set udg_Warden=u
call SaveStr(udg_hash,h,2,"Agi")
call SaveStr(udg_hash,h,3,"Melee")
set aganime="При использовании Скачок, при атаке ваша следущая цель получить максимальное количество стаков Неостановимая жестокость"
call EnableTrigger(gg_trg_WardenAtk)
call TriggerRegisterUnitEvent(gg_trg_killer,u,EVENT_UNIT_SPELL_EFFECT)
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00DD|r\nBeepный бpocoк, дaeт 20/40/60/80/100+20%лoвкocть aтaки нa 8 ceк. Учитывaт 25%вpeмeннoй лoвкocти, нo ycиливaeтcя 50%(пoвышeния aтaки)\nHeyлoвимaя тeнь, пoвышeны дo 8/16/24/32/36% yклoнeниe и 15% шaнc кpитa\n Heyдepжимocть, пoвышeнo вpeмя дeйcтвиe дo 30 ceк\nМacтep нoжeй:|nУбийcтвo вызывaeт эффeкт \"Эйфopия\" нa 10%ypoвeнь цeли ceк. He дeйcтвyeт пpи yбийcтвe вpaгoв c ypoвнeм нижe 3. Beepный бpocoк, дaeт 20%лoвкocть aтaки и 125/250/375/500/525+250%лoвкocть HP"
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Mod, Mage|r\nBeepный бpocoк, бaзoвый ypoн в 2 paзa. Пoвышeн ypoн oт Hoжeй нa лoвкocть\nCкaчoк. Kидaeт 2 нoжa oт yмeния Beepный бpocoк в cлyчaйныx вpaгoв вoкpyг тoчки тeлeпopтaции\nМacтep нoжeй:\nBaши aтaки нaнocят нa 15% мeньшe ypoнa, Mod: 10% шaнc нaнecти 50%лoвкocть ypoнa вpaгaм вoкpyг гepoя.\nBeepный бpocoк. Пoвышeн ypoн oт нoжeй нa 2*лoвкocть eд ypoнa.\nCкaчoк. Пoвышeнo кoличecтвo нoжeй дo 4 eд. B тeчeнии 3 ceк гepoй пoлyчaeт нa 10% мeньшe ypoнa."
set tal=2
elseif GetUnitTypeId(u)=='U01L' then
set s__Heroes_Pass_1sec_1[sHero[ihh]]="Grob_D_W"
set udg_Grob=u
call SaveStr(udg_hash,h,2,"Str")
call SaveStr(udg_hash,h,3,"Melee")
call TriggerRegisterUnitEvent(gg_trg_GrobSkills,u,EVENT_UNIT_SPELL_EFFECT)
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00Mage|r\nПoглoтить тpyпы, пoвышeн пpиpocт cилы c 7 дo 8 eд.\nKиcлoтныe жyки, тaкжe тeпepь взpывaютcя и пpи пoявлeнии нaнocя 25/50/75/100/125+cилa eд. ypoнa.\nTлeниe, cтaнoвитcя пepeключaeмoй cпocoбнocтью и бoльшe нe тpeбyeт мaны (Moжнo yдepживaть в aктивнoм cocтoянии дo бecкoнeчнocти).\nЗaкoпaтьcя, пoвышeн ypoн в двa paзa.\nKoнвepтaция, дoпoлнитeльнo пoвышaeтcя cилy нa 20% oт вceй cилы."
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Tank|r\nPаз в 40 сек, блoкиpyeт cмepтeльный ypoн и вoccтaнaвливaeт (cилa*2 + 10% здopoвья) здopoвья\nПoглoтить тpyпы, дoпoлнитeльнo иcцeляeт гepoя нa 20% oт мac. здopoвья|r eд. здopoвья\nKиcлoтныe жyки, пpи иcпoльзoвaнии пoнижaют вxoдящий пo гepoю ypoн нa 50% в тeчeнии 5 ceк.\nПaнциpь c шипaми, дoпoлнитeльнo дaeт 3/6/9/12/15 зaщиты.\nПocлe 50 ypoвня гepoй вoccтaнaвливaeт 0.5% здopoвья кaждyю ceкyндy."
set tal=2
elseif GetUnitTypeId(u)=='N007' or GetUnitTypeId(u)=='N07J' then
set i=0
loop
exitwhen i>7
call SetPlayerTechMaxAllowed(Player(i),'N007',0)
call SetPlayerTechMaxAllowed(Player(i),'N07J',0)
set i=i+1
endloop
call SaveStr(udg_hash,h,2,"Int")
call SaveStr(udg_hash,h,3,"Melee")
call TriggerRegisterUnitEvent(gg_trg_OrderJass,GetTriggerUnit(),EVENT_UNIT_ISSUED_ORDER)
call TriggerRegisterUnitEvent(gg_trg_Reptiloid,u,EVENT_UNIT_SPELL_EFFECT)
set udg_MurkyD=(udg_MurkyD+1)
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00Mod|r\nApoмopфoзы. Lvlup: +3 aтaки\nЭкcплoзия. Пoмeчaeт цeль нa 10 ceк. Mod: нaнocит 20/40/60/80/100+25%paзyм ypoнa и вoccтaнaвливaeт 25% дaннoгo ypoнa eд. здopoвья.\nПepeгpyзкa. Гepoй иcцeляeтcя нa 20%здopoвья и в тeчeнии 12 ceк пoлyчaeт 200/400/600/800+paзyм*3 здopoвья, 10%разум ед защиты и 10/20/30/40/50+50%paзyм aтaки (уcиливaeтcя на 50%). Пocлe 50 ypoвня +100% бoнуca здopoвья и aтaки\nСпособность 20 уровня: Tpeзyбeц Пoceйдoнa (Mod)"
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Mage|r\nЭкcплoзия. B тeчeнии 3 ceк цeль eжeceкyнднo удaряeт мoлния нaнocящая 40/80/120/160/200+50%paзyм ypoнa вpaгaм вoкpyг нee. Пocлeдняя мoлния нaнocит 200%ypoна и oглyшaeт цeль нa 0.5/1 ceк\nПepeгpyзкa. Cпycтя 0.25 ceк вызывaeт втopyю вoлнy, кoтopaя имeeт нa 50% бoльшe oблacти вoздeйcтвия и нa 50% мeньшe ypoнa\nДeмopaлизaция, зaдeтыe вpaги в тeчeнии 4/5/6/7/8 ceк пoлyчaют нa 30% бoльшe ypoнa oт вaшиx cпocoбнocтeй. Пocлe 50 ypoвня эффeкт пoвышaeт ypoн дo 60%\nСпособность 20 уровня: Aннигиляция (Active)"
set tal=2
elseif GetUnitTypeId(u)=='E004' then
call SaveStr(udg_hash,h,2,"Agi")
call SaveStr(udg_hash,h,3,"Melee")
call TriggerRegisterUnitEvent(gg_trg_RaiderSkills,u,EVENT_UNIT_SPELL_EFFECT)
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00DD|r\nЛoвчий, дaeт 30%(бaзoвaя aтaкa) eд aтaки в тeчeнии 9 ceк. Пocлe 50 ypoвня бoнyc ycилeн в 2 paaз\nPeв. Пoвышaeт зaщитy влaдeльцa нa 20%лoвкocть в тeчeнии 4 ceк.\nCпocoбнocть E: Bынocливocть opкa\nHaбeг, нaнocит ypoн и пoвышaeт бaзoвyю лoвкocть гepoя в двa paзa в тeчeнии 12 ceк"
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Summon|r\n-50% иcxoдящeгo ypoнa (+)\nHoвaя cпocoбнocть Cтapый дpyг, пpи иcпoльзoвaнии пpизывaeт вoлкa\nPeв, тeпepь paбoтaeт и нa нe-гepoeв\nCпocoбнocть E: Aypa вынocливocти\nHaбeг, пpизывaeт 4 вoлкoв c вpeмeнeм жизни 25 ceк"
set tal=2
elseif GetUnitTypeId(u)=='N04I' then
set udg_Gydra=u
call SaveStr(udg_hash,h,2,"Str")
call SaveStr(udg_hash,h,3,"Range")
set aganime="Сильный выстрел, +50% количество снарядов"
call TriggerRegisterUnitEvent(gg_trg_Gydra,u,EVENT_UNIT_SPELL_EFFECT)
set udg_MurkyD=udg_MurkyD+1
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00Regen|r\n-4*сила HP\nHeocтaнoвимый pocт, +2 HP reg\nCильный выcтpeл, +1.75 HP reg ypoн\nГpoмoвaя пocтyпь, в тeчeнии 8 ceк гepoй нaнocит 10/20/30/40/50+1.75HP reg в ceк.\nCпocoбнocть E: Бeccмepтиe гидpы, вoccтaнaвливaeт здopoвьe в ceк.\nCпocoбнocть R: Тpи гoлoвы, aтaкyeт cлyчaйнyю цeль и вoccтaнaвливaeт здopoвьe"
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00DD|r\nHeocтaнoвимый pocт, +2 aтaки\nCильный выcтpeл, +50%aтaкa ypoн\nГpoмoвaя пocтyпь, +100% aтaкa ypoн\nCилa гидpы, пaccивнo дaeт 20/40/60/80/100+25%бaзoвaя eд aтaки\nМyльтишoт, Гидpa мoжeт пopaжaть дo 4 цeлeй зa выcтpeл. +10% paдиycy cплeшa"
set tal=2
elseif GetUnitTypeId(u)=='E00W' or GetUnitTypeId(u)=='E011' then
set i=0
loop
exitwhen i>7
call SetPlayerTechMaxAllowed(Player(i),'E00W',0)
call SetPlayerTechMaxAllowed(Player(i),'E011',0)
set i=i+1
endloop
set udg_Shinobi=u
call SaveStr(udg_hash,h,2,"Agi")
call SaveStr(udg_hash,h,3,"Melee")
call TriggerRegisterUnitEvent(gg_trg_Shinobi,u,EVENT_UNIT_SPELL_EFFECT)
set s__PlayerStruct_hs1[sPlayer[id]]="|cFFC9AD00DD|r\nBзpывнoй cюpикeн, вoccтaнaвливaeт 150%лoвкocть здopoвья\nТeмный дpaкoн\nBзpывнoй cюpикeн, пoнижaeт зaщитy цeли нa 4/6/9/11/15 eд. нa 8 ceк.\nPывoк. Пocлe пpимeнeния дaeт 16% шaнc нa 2/2.5/3/3.5/4-кpaтный ypoн в тeчeнии 8 ceк.\n\nХитpый лиc\nAтaкa Cинoби, Mod: c 40% шaнcoм нaнocит 75%лoвкocть eд ypoнa цeли. Тип ypoнa: 50%Физикa + 50%Мaгия\n\nCпocoбнocть R: Heбecный дpaкoн. Гepoй пoлyчaeт +50+20%лoвкocть зaщиты, a тaкжe пoлyчaeт дoпoлнитeльный эффeкт oт cтиля бoя: Тeмный дpaкoн. Пoвышaeт cилy aтaки нa 100%; Хитpый лиc. Baши aтaки c 30% шaнcoм мoгyт вызвaть втopoe cpaбaтывaниe мoдификaтopoв.  Длитeльнocть - 30 ceк. Пepeзapядкa 90 ceк."
set s__PlayerStruct_hs2[sPlayer[id]]="|cFFC9AD00Caster|r\n+1 лoвкocти зa пoвышeнии ypoвня\nТeмный дpaкoн\nBзpывнoй cюpикeн, иcцeляeт нa 150%лoвкocть eд.\nPывoк. Гepoй пoлyчaeт нeyязвимocть к ypoнy в тeчeнии 0.75 ceк.\nДымoвaя зaвeca, дaeт 100% yклoнeниe ecли гepoй нaxoдитcя в зaвece.\n\nХитpый лиc\nПoвышeнo ycилeниe ypoнa oт cпocoбнocтeй дo 325%\nДымoвaя зaвeca, тeпepь нaнocит 25/50/75/100/125+50%Лoвкocть eд. ypoнa вo вpeмя cвoeгo дeйcтвия\n\nCпocoбнocть R: Бoмбa Хвocтaтoгo. Cтapoe yмeниe бeз измeнeний"
set tal=2
elseif GetUnitTypeId(u)=='H000' then
set s__Heroes_Type[sHero[ihh]]=1
call SaveStr(udg_hash,h,2,"Str")
call SaveStr(udg_hash,h,3,"Range")
set aganime="+40% к получаемому и макс. получаемому золоту\nБоевая готовность. Дает 200+75%базовой силы ед. силы в течении 10 сек"
set udg_HeroGold[ID]=udg_HeroGold[ID]+0.20
set udg_HeroGoldMax[ID]=udg_HeroGoldMax[ID]+0.20
call TriggerRegisterUnitEvent(gg_trg_Tank,u,EVENT_UNIT_SPELL_EFFECT)
set bj_groupEnumTypeId='ncop'
call GroupEnumUnitsOfPlayer(g,pl,filterGetUnitsOfPlayerAndTypeId)
set bj_lastCreatedUnit=FirstOfGroup(g)
call GroupClear(g)
call CreateUnit(pl,'h001',GetUnitX(bj_lastCreatedUnit)-80,GetUnitY(bj_lastCreatedUnit)+80,bj_UNIT_FACING)
call UnitAddItemByIdSwapped('I09I',u)
call UnitAddItemByIdSwapped('I09I',u)
call UnitAddItemByIdSwapped('I09I',u)
call RemoveItem(UnitItemInSlot(u,0))
elseif GetUnitTypeId(u)=='H02T' then
call SaveStr(udg_hash,h,2,"Str")
call SaveStr(udg_hash,h,3,"Melee")
set aganime="+40% к получаемому и макс. получаемому золоту\nИмпульс. При использовании герой получает удвоенный бонус атаки от улучшений и получает на 50% меньше урона в течении 10 сек"
set s__Heroes_Type[sHero[ihh]]=1
set udg_HeroGold[ID]=udg_HeroGold[ID]+0.20
set udg_HeroGoldMax[ID]=udg_HeroGoldMax[ID]+0.20
call TriggerRegisterUnitEvent(gg_trg_MechGolem,u,EVENT_UNIT_SPELL_EFFECT)
call EnableTrigger(gg_trg_lvlupgolem)
set bj_groupEnumTypeId='ncop'
call GroupEnumUnitsOfPlayer(g,pl,filterGetUnitsOfPlayerAndTypeId)
set bj_lastCreatedUnit=FirstOfGroup(g)
call GroupClear(g)
call CreateUnit(pl,'h02U',GetUnitX(bj_lastCreatedUnit)-80,GetUnitY(bj_lastCreatedUnit)+80,bj_UNIT_FACING)
call UnitAddItemByIdSwapped('I09I',u)
call UnitAddItemByIdSwapped('I09I',u)
call UnitAddItemByIdSwapped('I09I',u)
call RemoveItem(UnitItemInSlot(u,0))
elseif GetUnitTypeId(u)=='H04O' then
set s__Heroes_Type[sHero[ihh]]=1
call SaveStr(udg_hash,h,2,"Agi")
call SaveStr(udg_hash,h,3,"Range")
set aganime="+40% к получаемому и макс. получаемому золоту\n+20% к наносимому урону (умножается)"
set udg_HeroGold[ID]=udg_HeroGold[ID]+0.20
set udg_HeroGoldMax[ID]=udg_HeroGoldMax[ID]+0.20
call TriggerRegisterUnitEvent(gg_trg_Helicopter,u,EVENT_UNIT_SPELL_EFFECT)
set bj_groupEnumTypeId='ncop'
call GroupEnumUnitsOfPlayer(g,pl,filterGetUnitsOfPlayerAndTypeId)
set bj_lastCreatedUnit=FirstOfGroup(g)
call GroupClear(g)
call CreateUnit(pl,'h04P',GetUnitX(bj_lastCreatedUnit)-80,GetUnitY(bj_lastCreatedUnit)+80,bj_UNIT_FACING)
call UnitAddItemByIdSwapped('I09I',u)
call UnitAddItemByIdSwapped('I09I',u)
call UnitAddItemByIdSwapped('I09I',u)
call RemoveItem(UnitItemInSlot(u,0))
elseif GetUnitTypeId(u)=='H03R' then
call SaveStr(udg_hash,h,2,"Int")
call SaveStr(udg_hash,h,3,"Range")
set aganime="Дары природы, ускорена перезарядка с 8 до 6 сек.\nБолотные твари, призывает еще 4 болотные твари с эффектом Дары природы, но имеющие время жизни 40 сек"
call TriggerRegisterUnitEvent(gg_trg_RenaSkills,u,EVENT_UNIT_SPELL_EFFECT)
elseif GetUnitTypeId(u)=='Otch' then
call SaveStr(udg_hash,h,2,"Str")
call SaveStr(udg_hash,h,3,"Melee")
call TriggerRegisterUnitEvent(gg_trg_SwordMaster_Skills,u,EVENT_UNIT_SPELL_EFFECT)
elseif GetUnitTypeId(u)=='Oshd' or GetUnitTypeId(u)=='O013' then
set i=0
loop
exitwhen i>7
call SetPlayerTechMaxAllowed(Player(i),'Oshd',0)
call SetPlayerTechMaxAllowed(Player(i),'O013',0)
set i=i+1
endloop
call SaveStr(udg_hash,h,2,"Int")
call SaveStr(udg_hash,h,3,"Range")
call SetUnitAbilityLevel(u,'A14S',2)
call TriggerRegisterUnitEvent(gg_trg_Engineer_Skills,u,EVENT_UNIT_SPELL_EFFECT)
call SaveStr(udg_hash,h,StringHash("CommandQ"),"1) Превращается в Защитную башню, -25% к скорости атаки, наносит урон по области, и +300 к дальности атаки и +20% здоровья\n2) Превращается в Магическую башню, раз в 4 сек атака башни вызывает цепную молнию отскакивающую до 6 противников и наносящую 20/40/60/80/100+разум ед. урона\n3) Превращается в Сторожевую башню, -28% скорости атаки, получает мультишот на 5 целей\n4) Превращается в Дальнобойную башню, +600 к дальности атаки, получает 35% шанс нанести 3-кратный урон и 15% шанс оглушить слабого противника на 2 сек.")
call SaveStr(udg_hash,h,StringHash("CommandF"),"1) Регенерация 2% здоровья в сек и 25% шанс уклонится от атаки\n2) +30% к урону. Раз в 20 сек атака башни повышается на разум*2 ед. в течении 10 сек\n3) Каждая атака имеет 20% шанс нанести 50+разум ед. урона и восстановить 20% от данного значения\n4) +20% к наносимому урону и +20% к уменьшению входящего урона\n5) +40% к здоровью и +2% макс. здоровья обратного урона ")
endif
if No_hero==false and Is_Mech==false then
set a=0
if GetPlayerTechCount(pl,'R02B',true)>=10 then
set a='I06M'
elseif GetPlayerTechCount(pl,'R02B',true)>=8 then
set a='I03M'
elseif GetPlayerTechCount(pl,'R02B',true)>=5 then
set a='I06I'
elseif GetPlayerTechCount(pl,'R02B',true)>=2 then
set a='I01M'
else
set a='stel'
endif
if a>0 then
set bj_lastCreatedItem=CreateItem(a,GetUnitX(u),GetUnitY(u))
call UnitAddItem(u,bj_lastCreatedItem)
endif
endif
call SetPlayerStateBJ(pl,PLAYER_STATE_RESOURCE_GOLD,GetPlayerState(pl,PLAYER_STATE_RESOURCE_GOLD)+2000)
call SaveStr(udg_hash,h,StringHash("Aganime"),aganime)
if GetUnitTypeId(u)=='U00V' then
set bj_lastCreatedUnit=CreateUnit(pl,'n074',GetRectCenterX(gg_rct_StartPlace),GetRectCenterY(gg_rct_StartPlace),bj_UNIT_FACING)
call SetCameraBoundsToRectForPlayerBJ(pl,GetWorldBounds())
if GetLocalPlayer()==pl then
call PanCameraToTimed(GetRectCenterX(gg_rct_StartPlace),GetRectCenterY(gg_rct_StartPlace),0)
endif
set udg_Crow=bj_lastCreatedUnit
call TriggerRegisterUnitEvent(gg_trg_CrowSkills,bj_lastCreatedUnit,EVENT_UNIT_SPELL_EFFECT)
set bj_groupEnumTypeId='ncop'
call GroupEnumUnitsOfPlayer(g,pl,filterGetUnitsOfPlayerAndTypeId)
set bj_lastCreatedUnit=FirstOfGroup(g)
call GroupClear(g)
call ReplaceUnitBJ(bj_lastCreatedUnit,'n073',bj_UNIT_STATE_METHOD_DEFAULTS)
call EnableTrigger(gg_trg_Vorons_Towers)
call EnableTrigger(gg_trg_CrowExp)
call EnableTrigger(gg_trg_CrowSkillCheck)
call EnableTrigger(gg_trg_CrowCrafting)
call TriggerRegisterUnitEvent(gg_trg_CrowSkills,bj_lastReplacedUnit,EVENT_UNIT_SPELL_EFFECT)
set udg_CrowExp[1]=400
set udg_CrowExp[2]=900
set udg_CrowExp[3]=1600
set udg_CrowExp[4]=2500
set udg_CrowExp[5]=3750
set udg_CrowExp[6]=5500
set udg_CrowExp[7]=7500
set udg_CrowExp[8]=10000
set udg_CrowExp[9]=14000
set udg_CrowExp[10]=20000
set udg_CrowLeveling[2]=1
set udg_CrowLeveling[3]=udg_CrowExp[udg_CrowLeveling[2]]
set udg_HeroGold[ID]=-3.00
call RemoveUnit(u)
call FlushChildHashtable(udg_hash,h)
elseif GetUnitTypeId(u)=='U02A' then
call GroupAddUnit(udg_HeroBuild,u)
call SaveStr(udg_hash,h,2,"Agi")
call SaveStr(udg_hash,h,3,"Range")
set bj_lastCreatedUnit=CreateUnit(pl,'h05A',GetRectCenterX(gg_rct_StartPlace),GetRectCenterY(gg_rct_StartPlace),bj_UNIT_FACING)
set udg_Thing=CreateUnit(pl,'n07E',GetRectCenterX(gg_rct_StartPlace),GetRectCenterY(gg_rct_StartPlace),bj_UNIT_FACING)
call TriggerRegisterUnitEvent(gg_trg_Thing,udg_Thing,EVENT_UNIT_SPELL_EFFECT)
call EnableTrigger(gg_trg_ThingDead)
call TriggerRegisterPlayerUnitEvent(gg_trg_ThingBody,pl,EVENT_PLAYER_UNIT_SPELL_EFFECT,null)
call SetCameraBoundsToRectForPlayerBJ(pl,GetWorldBounds())
call PanCameraToTimedForPlayer(pl,GetRectCenterX(gg_rct_StartPlace),GetRectCenterY(gg_rct_StartPlace),0)
set bj_groupEnumTypeId='ncop'
call GroupEnumUnitsOfPlayer(g,pl,filterGetUnitsOfPlayerAndTypeId)
set bj_lastCreatedUnit=FirstOfGroup(g)
call GroupClear(g)
set x=GetUnitX(bj_lastCreatedUnit)-80
set y=GetUnitY(bj_lastCreatedUnit)+80
set bj_lastCreatedUnit=CreateUnit(pl,'n07F',x,y,bj_UNIT_FACING)
call TriggerRegisterUnitEvent(gg_trg_ThingUpgrade,bj_lastCreatedUnit,EVENT_UNIT_RESEARCH_FINISH)
set udg_ThingNumber=1
set udg_ThingSummon[1]='ugho'
set udg_ThingSummon[2]='ugho'
set udg_ThingSummon[3]='ugho'
set udg_ThingSummon[4]='ugho'
set udg_ThingSummon[5]='ugho'
set udg_HeroGold[ID]=udg_HeroGold[ID]+0.40
set udg_HeroGoldMax[ID]=udg_HeroGoldMax[ID]+0.40
set t=CreateTimer()
set ht=GetHandleId(t)
call SaveInteger(Hash,ht,0,ID)
call TimerStart(t,.1,true,function Trig_ThingBaseWait)
endif
if tal>0 then
set bj_groupEnumTypeId='ncop'
call GroupEnumUnitsOfPlayer(g,pl,filterGetUnitsOfPlayerAndTypeId)
set bj_lastCreatedUnit=FirstOfGroup(g)
call GroupClear(g)
call UnitAddAbility(bj_lastCreatedUnit,'A0ZH')
if tal<3 then
call UnitRemoveAbility(bj_lastCreatedUnit,'A1CE')
endif
endif
call DestroyGroup(g)
set pl=null
set u=null
set g=null
set t=null
endfunction

```

### 风险函数 #9 (风险评分: 10)
```jass
function Trig_UseItemJass_Actions takes nothing returns nothing
local unit caster=GetTriggerUnit()
local integer h=GetHandleId(caster)
local integer ID=GetPlayerId(GetOwningPlayer(caster))+1
local item Item=GetManipulatedItem()
local integer hi=GetHandleId(Item)
local unit u
local timer t
local integer ht
local integer a
local integer b
local integer c
local integer d
local integer e
local integer lvl
local integer drop
local real x
local real y
local real x1
local real y1
local real dmg
local group g=CreateGroup()
local group gt
local location p
local location p2
local integer highstat
local integer ihh=LoadInteger(udg_hash,h,5)
local integer iuh=LoadInteger(Hash,h,0)
set a=GetHeroStr(caster,true)
set b=GetHeroAgi(caster,true)
set c=GetHeroInt(caster,true)
if a>=b then
if a>=c then
set highstat=a
else
set highstat=c
endif
else
if b>=c then
set highstat=b
else
set highstat=c
endif
endif
if GetItemTypeId(Item)=='I0DG' then
call SummonStats(false,0,120,caster,caster)
endif
if GetItemTypeId(Item)=='mcri' then
set a=0
loop
exitwhen a>=8
set bj_lastCreatedUnit=CreateUnit(Player(ID-1),'hpea',GetUnitX(caster),GetUnitY(caster),bj_UNIT_FACING)
set a=a+1
endloop
endif
if GetItemTypeId(Item)=='I01P' then
set a=0
loop
exitwhen a>=8
set bj_lastCreatedUnit=CreateUnit(Player(ID-1),'opeo',GetUnitX(caster),GetUnitY(caster),bj_UNIT_FACING)
set a=a+1
endloop
endif
if GetItemTypeId(Item)=='I0ET' then
call SetUnitState(caster,UNIT_STATE_LIFE,GetUnitState(caster,UNIT_STATE_LIFE)+500.+0.05*GetUnitState(caster,UNIT_STATE_MAX_LIFE))
call FoTDeath(caster,GetUnitX(caster),GetUnitY(caster),false)
endif
if GetItemTypeId(Item)=='I054' and GetPlayerState(GetOwningPlayer(caster),PLAYER_STATE_RESOURCE_GOLD)>=12500 then
call RemoveItem(Item)
set b=12500
call SetPlayerStateBJ(Player(ID-1),PLAYER_STATE_RESOURCE_GOLD,GetPlayerState(Player(ID-1),PLAYER_STATE_RESOURCE_GOLD)-b)
call UnitAddItemByIdSwapped('I0DZ',caster)
elseif GetItemTypeId(Item)=='I0DZ' and GetPlayerState(GetOwningPlayer(caster),PLAYER_STATE_RESOURCE_GOLD)>=22000 then
call RemoveItem(Item)
set b=22000
call SetPlayerStateBJ(Player(ID-1),PLAYER_STATE_RESOURCE_GOLD,GetPlayerState(Player(ID-1),PLAYER_STATE_RESOURCE_GOLD)-b)
call UnitAddItemByIdSwapped('I0DY',caster)
elseif GetItemTypeId(Item)=='I02J' then
call SetUnitManaBJ(caster,GetUnitStateSwap(UNIT_STATE_MANA,caster)+99.00+25.00*I2R(GetHeroLevel(caster)))
elseif GetItemTypeId(Item)=='I081' then
set x=GetUnitX(caster)
set y=GetUnitY(caster)
set a=1
loop
exitwhen a>12
set x1=x+400.*Cos(a*30.*bj_DEGTORAD)
set y1=y+400.*Sin(a*30.*bj_DEGTORAD)
call DestroyEffect(AddSpecialEffect("Abilities\\Spells\\Undead\\AnimateDead\\AnimateDeadTarget.mdl",x1,y1))
set u=CreateUnit(Player(ID-1),'nsw2',x1,y1,a*30.)
call UnitApplyTimedLife(u,'BTLF',40.)
set a=a+1
endloop
elseif GetItemTypeId(Item)=='I07F' then
if IsUnitInGroup(caster,udg_ShamanItem)then
call GroupRemoveUnitSimple(caster,udg_ShamanItem)
call UnitRemoveAbilityBJ('A0W6',caster)
call UnitRemoveAbilityBJ('A0DK',caster)
else
call GroupAddUnitSimple(caster,udg_ShamanItem)
call UnitAddAbilityBJ('A0W6',caster)
call UnitAddAbilityBJ('A0DK',caster)
endif
elseif GetItemTypeId(Item)=='I07K' then
call RemoveItem(Item)
set a=GetRandomInt(1,5)
if a==1 then
set b=R2I(GetRandomInt(2500,4500)*AllGold[ID])
call SetPlayerStateBJ(Player(ID-1),PLAYER_STATE_RESOURCE_GOLD,GetPlayerState(Player(ID-1),PLAYER_STATE_RESOURCE_GOLD)+b)
set GoldNT[ID]=GoldNT[ID]+b
call DisplayTimedTextToForce(bj_FORCE_PLAYER[ID-1],20.00,"|cFFFFDC00Вы получили "+I2S(b)+" золота!")
elseif a==2 then
set b=GetRandomInt(2500,4500)
call DisplayTimedTextToForce(bj_FORCE_PLAYER[ID-1],20.00,"|cFFFFDC00Вы получили "+I2S(b)+" опыта!")
call AddHeroXPSwapped(b,caster,true)
elseif a==3 then
set b=GetRandomInt(17,27)
call DisplayTimedTextToForce(bj_FORCE_PLAYER[ID-1],20.00,"|cFFFFDC00Вы получили "+I2S(b)+" силы!")
call ModifyHeroStat(bj_HEROSTAT_STR,caster,bj_MODIFYMETHOD_ADD,b)
elseif a==4 then
set b=GetRandomInt(17,27)
call DisplayTimedTextToForce(bj_FORCE_PLAYER[ID-1],20.00,"|cFFFFDC00Вы получили "+I2S(b)+" ловкости!")
call ModifyHeroStat(bj_HEROSTAT_AGI,caster,bj_MODIFYMETHOD_ADD,b)
elseif a==5 then
set b=GetRandomInt(17,27)
call DisplayTimedTextToForce(bj_FORCE_PLAYER[ID-1],20.00,"|cFFFFDC00Вы получили "+I2S(b)+" разума!")
call ModifyHeroStat(bj_HEROSTAT_INT,caster,bj_MODIFYMETHOD_ADD,b)
endif
else
endif
if GetItemTypeId(Item)=='I0CD' then
set bj_lastCreatedUnit=CreateUnit(Player(ID-1),'h009',GetUnitX(caster),GetUnitY(caster),bj_UNIT_FACING)
call UnitAddAbility(bj_lastCreatedUnit,'A0YL')
call IssueTargetOrder(bj_lastCreatedUnit,"banish",GetManipulatingUnit())
call UnitApplyTimedLife(bj_lastCreatedUnit,'BTLF',.75)
endif
if GetItemTypeId(Item)=='I03P' then
set bj_lastCreatedUnit=CreateUnit(Player(ID-1),'h009',GetUnitX(caster),GetUnitY(caster),bj_UNIT_FACING)
call UnitAddAbility(bj_lastCreatedUnit,'A05B')
call IssueImmediateOrder(bj_lastCreatedUnit,"tranquility")
call UnitApplyTimedLife(bj_lastCreatedUnit,'BTLF',35.)
endif
if GetItemTypeId(GetManipulatedItem())=='I04B' then
set bj_forLoopAIndex=1
loop
exitwhen bj_forLoopAIndex>9
set x1=GetRandomReal(256.00,500.00)
set y1=GetRandomReal(0.00,360.00)
set x=GetUnitX(caster)+x1*Cos(y1*bj_DEGTORAD)
set y=GetUnitY(caster)+x1*Sin(y1*bj_DEGTORAD)
set bj_lastCreatedUnit=CreateUnit(GetOwningPlayer(caster),'ngh2',x,y,GetRandomReal(0,360.00))
call DestroyEffect(AddSpecialEffect("Abilities\\Spells\\Human\\Invisibility\\InvisibilityTarget.mdl",x,y))
call UnitApplyTimedLife(bj_lastCreatedUnit,'BTLF',20.)
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
endif
if GetItemTypeId(GetManipulatedItem())=='I01N' then
call SetPlayerTechResearchedSwap('R00G',(GetPlayerTechCountSimple('R00G',GetOwningPlayer(GetManipulatingUnit()))+1),GetOwningPlayer(GetManipulatingUnit()))
call KillUnit(GetManipulatingUnit())
set u=CreateUnit(Player(ID-1),'n027',GetUnitX(caster),GetUnitY(caster),bj_UNIT_FACING)
call SetUnitAbilityLevel(u,'A0E4',GetPlayerTechCountSimple('R00G',GetOwningPlayer(GetManipulatingUnit())))
call SetUnitAbilityLevel(u,'A09C',GetPlayerTechCountSimple('R00G',GetOwningPlayer(GetManipulatingUnit())))
call UnitApplyTimedLife(u,'BTLF',100.)
call SetUnitVertexColor(u,255,150,0,150)
set x1=GetUnitState(caster,UNIT_STATE_MAX_LIFE)
call UnitAddAbility(u,'A007')
call SummonStats(true,R2I(0.5*x1),R2I(0.1*x1),u,caster)
call UnitRemoveAbility(u,'A007')
set x=GetUnitX(u)
set y=GetUnitY(u)
call DestroyEffect(AddSpecialEffect("Abilities\\Spells\\Human\\FlameStrike\\FlameStrikeTarget.mdl",x,y))
set bj_forLoopAIndex=1
loop
exitwhen bj_forLoopAIndex>10
set x1=x+400.*Cos(bj_forLoopAIndex*36.*bj_DEGTORAD)
set y1=y+400.*Sin(bj_forLoopAIndex*36.*bj_DEGTORAD)
call DestroyEffect(AddSpecialEffect("Objects\\Spawnmodels\\Undead\\UDeathMedium\\UDeath.mdl",x1,y1))
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
else
endif
if GetItemTypeId(Item)=='I08N' then
call TempStats(caster,0,0,0,0,20,0,20)
elseif GetItemTypeId(Item)=='I02X' then
set x=GetUnitX(caster)
set y=GetUnitY(caster)
set udg_Drop2=ID-1
call GroupEnumUnitsInRange(g,x,y,450.,Bool_Filter_ID_Ally)
call RandomUnitFromGroup(10,g)
loop
set u=FirstOfGroup(g)
exitwhen u==null
set bj_lastCreatedUnit=CreateUnit(Player(ID-1),'h009',x,y,bj_UNIT_FACING)
call UnitApplyTimedLife(bj_lastCreatedUnit,'BTLF',.75)
call UnitAddAbility(bj_lastCreatedUnit,'A0A6')
call IssueTargetOrder(bj_lastCreatedUnit,"innerfire",u)
call GroupRemoveUnit(g,u)
endloop
elseif GetItemTypeId(Item)=='I01R' then
call CreateTextTagUnitBJ((I2S(R2I(GetUnitState(caster,UNIT_STATE_MANA)))+" X 10!"),GetManipulatingUnit(),0,11.00,100,60.00,60.00,0)
set udg_TEXT=GetLastCreatedTextTag()
call SetTextTagVelocityBJ(udg_TEXT,100.00,GetRandomReal(80.00,120.00))
call SetTextTagSuspendedBJ(udg_TEXT,false)
call SetTextTagPermanentBJ(udg_TEXT,false)
call SetTextTagLifespanBJ(udg_TEXT,4.00)
call SetTextTagFadepointBJ(udg_TEXT,3.00)
set x=GetUnitX(caster)
set y=GetUnitY(caster)
set dmg=GetUnitState(caster,UNIT_STATE_MANA)
set udg_Drop2=ID-1
call GroupEnumUnitsInRange(g,x,y,900,Bool_Filter_ID)
call RandomUnitFromGroup(10,g)
loop
set u=FirstOfGroup(g)
exitwhen u==null
call UnitDamageTarget(caster,u,dmg,false,false,ATTACK_TYPE_NORMAL,DAMAGE_TYPE_MAGIC,WEAPON_TYPE_AXE_MEDIUM_CHOP)
call DestroyEffect(AddSpecialEffectTarget("Abilities\\Spells\\Human\\MarkOfChaos\\MarkOfChaosTarget.mdl",u,"origin"))
call GroupRemoveUnit(g,u)
endloop
call SetUnitState(caster,UNIT_STATE_MANA,GetUnitState(caster,UNIT_STATE_MANA)*0.5)
elseif GetItemTypeId(Item)=='I068' then
set x=GetUnitX(caster)
set y=GetUnitY(caster)
set dmg=GetHeroLevel(caster)*5+1.*(GetHeroInt(caster,true)+GetHeroAgi(caster,true)+GetHeroStr(caster,true))
set udg_Drop2=ID-1
call GroupEnumUnitsInRange(g,x,y,900,Bool_Filter_ID)
loop
set u=FirstOfGroup(g)
exitwhen u==null
call UnitDamageTarget(caster,u,dmg,false,false,ATTACK_TYPE_NORMAL,DAMAGE_TYPE_MAGIC,WEAPON_TYPE_AXE_MEDIUM_CHOP)
call DestroyEffect(AddSpecialEffect("Abilities\\Spells\\Other\\Monsoon\\MonsoonBoltTarget.mdl",GetUnitX(u),GetUnitY(u)))
call GroupRemoveUnit(g,u)
endloop
elseif GetItemTypeId(GetManipulatedItem())=='I00D' then
set a=GetRandomInt(1,6)
if a==1 then
set x=GetRandomReal(GetRectMinX(gg_rct_Field1),GetRectMaxX(gg_rct_Field1))
set y=GetRandomReal(GetRectMinY(gg_rct_Field1),GetRectMaxY(gg_rct_Field1))
set x1=x+Cos(bj_DEGTORAD)
set y1=y+Sin(bj_DEGTORAD)
set bj_lastCreatedItem=CreateItem('I00F',x1,y1)
elseif a==2 then
set x=GetRandomReal(GetRectMinX(gg_rct_Field2),GetRectMaxX(gg_rct_Field2))
set y=GetRandomReal(GetRectMinY(gg_rct_Field2),GetRectMaxY(gg_rct_Field2))
set x1=x+Cos(bj_DEGTORAD)
set y1=y+Sin(bj_DEGTORAD)
set bj_lastCreatedItem=CreateItem('I00F',x1,y1)
elseif a==3 then
set x=GetRandomReal(GetRectMinX(gg_rct_Field3),GetRectMaxX(gg_rct_Field3))
set y=GetRandomReal(GetRectMinY(gg_rct_Field3),GetRectMaxY(gg_rct_Field3))
set x1=x+Cos(bj_DEGTORAD)
set y1=y+Sin(bj_DEGTORAD)
set bj_lastCreatedItem=CreateItem('I00F',x1,y1)
elseif a==4 then
set x=GetRandomReal(GetRectMinX(gg_rct_Field4),GetRectMaxX(gg_rct_Field4))
set y=GetRandomReal(GetRectMinY(gg_rct_Field4),GetRectMaxY(gg_rct_Field4))
set x1=x+Cos(bj_DEGTORAD)
set y1=y+Sin(bj_DEGTORAD)
set bj_lastCreatedItem=CreateItem('I00F',x1,y1)
elseif a==5 then
set x=GetRandomReal(GetRectMinX(gg_rct_Field5),GetRectMaxX(gg_rct_Field5))
set y=GetRandomReal(GetRectMinY(gg_rct_Field5),GetRectMaxY(gg_rct_Field5))
set x1=x+Cos(bj_DEGTORAD)
set y1=y+Sin(bj_DEGTORAD)
set bj_lastCreatedItem=CreateItem('I00F',x1,y1)
elseif a==6 then
set x=GetRandomReal(GetRectMinX(gg_rct_Field6),GetRectMaxX(gg_rct_Field6))
set y=GetRandomReal(GetRectMinY(gg_rct_Field6),GetRectMaxY(gg_rct_Field6))
set x1=x+Cos(bj_DEGTORAD)
set y1=y+Sin(bj_DEGTORAD)
set bj_lastCreatedItem=CreateItem('I00F',x1,y1)
endif
elseif GetItemTypeId(GetManipulatedItem())=='I0AP' then
call RemoveItem(GetManipulatedItem())
call UnitAddItemByIdSwapped(ChooseRandomItemBJ(8),GetManipulatingUnit())
elseif GetItemTypeId(GetManipulatedItem())=='I0AS' then
set u=GetManipulatingUnit()
set udg_player=GetOwningPlayer(u)
call RemoveItem(GetManipulatedItem())
set bj_forLoopAIndex=1
loop
exitwhen bj_forLoopAIndex>6
set udg_ItemSave[bj_forLoopAIndex]=UnitItemInSlotBJ(u,bj_forLoopAIndex)
call UnitRemoveItemFromSlotSwapped(bj_forLoopAIndex,u)
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
if u==udg_CrowRTarget then
set udg_CrowRLogic=false
set udg_CrowRTarget=null
call DisplayTimedTextToForce(bj_FORCE_PLAYER[GetPlayerId(GetOwningPlayer(udg_Crow))],10.00,"|cFFFF5800Вы больше не привязаны к герою!|r")
else
endif
set h=GetHandleId(u)
set a=LoadInteger(udg_hash,h,5)
set s__Heroes_id[sHero[a]]=0
set a=LoadInteger(Hash,h,0)
set s__Units_id[sUnit[a]]=0
call FlushChildHashtable(udg_hash,h)
call FlushChildHashtable(Hash,h)
call RemoveUnit(u)
set x=GetRectCenterX(gg_rct_StartPlace)
set y=GetRectCenterY(gg_rct_StartPlace)
set u=CreateUnit(Player(ID-1),'U01N',x,y,bj_UNIT_FACING)
set udg_Hero[ID]=u
set udg_Leoric=u
set udg_HeroResTime[ID]=udg_HeroResTime[ID]-10
set h=GetHandleId(u)
call SaveReal(udg_hash,h,StringHash("HPRegenBonusMult"),1)
call SaveStr(udg_hash,h,2,"Str")
call SaveStr(udg_hash,h,3,"Melee")
call GroupAddUnit(udg_ug_Regen,u)
set a=SeekFreeHero(h)
set s__Heroes_Pass_1sec_1[sHero[a]]="F_LeoricSoul"
call SaveInteger(udg_hash,h,5,a)
set d=SeekFreeUnit(h)
call GroupAddUnit(udg_AllHeroes,u)
call SetHeroLevel(u,50,false)
call SetHeroStr(u,GetHeroStr(u,false)+KStr[ID],true)
call SetHeroAgi(u,GetHeroAgi(u,false)+KAgi[ID],true)
call SetHeroInt(u,GetHeroInt(u,false)+KInt[ID],true)
set a=Kdmg[ID]
set b=Khp[ID]
set c=Kmp[ID]
if a>0 then
call TakeHeroAttack(a,u)
endif
set s__Units_HP[sUnit[d]]=s__Units_HP[sUnit[d]]+b
set s__Units_MP[sUnit[d]]=s__Units_MP[sUnit[d]]+c
set bj_forLoopAIndex=1
loop
exitwhen bj_forLoopAIndex>6
call UnitAddItemSwapped(udg_ItemSave[bj_forLoopAIndex],u)
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
call DestroyEffect(AddSpecialEffect("war3mapImported\\AnnihilationBlast.mdx",x,y))
if GetLocalPlayer()==Player(ID-1)then
call PanCameraToTimed(x,y,0)
endif
call TransmissionFromUnitWithNameBJ(GetPlayersAll(),u,"Леорик",null,"Как вы осмелились осквернить мой склеп теплом жизни!?",bj_TIMETYPE_ADD,0.00,true)
call EnableTrigger(gg_trg_LeoricSkills)
elseif GetItemTypeId(GetManipulatedItem())=='I06Q' then
set x=GetUnitX(caster)
set y=GetUnitY(caster)
set dmg=4*GetHeroInt(caster,true)
call GroupDamage(x,y,400,caster,false,dmg,ATTACK_TYPE_NORMAL,DAMAGE_TYPE_MAGIC)
elseif GetItemTypeId(GetManipulatedItem())=='I0AI' then
set u=GetManipulatingUnit()
set a=50+highstat/10
call TempStats(u,a,a,a,0,0,0,PositiveDuration(caster,14))
elseif GetItemTypeId(GetManipulatedItem())=='kygh' then
if not LoadBoolean(udg_hash,h,StringHash("WatchDeath"))then
set t=CreateTimer()
set ht=GetHandleId(t)
call SaveUnitHandle(udg_hash,ht,0,caster)
call SaveInteger(udg_hash,ht,1,60)
call SaveBoolean(udg_hash,h,StringHash("WatchDeath"),true)
call TimerStart(t,1.,true,function WatchDeath)
endif
elseif GetItemTypeId(GetManipulatedItem())=='I0AR' then
call RemoveItem(GetManipulatedItem())
if GetUnitTypeId(caster)=='H02T' or GetUnitTypeId(caster)=='H000' or GetUnitTypeId(caster)=='H04O' or GetUnitTypeId(caster)=='H04Q' then
else
if GetUnitTypeId(caster)=='E002' or GetUnitTypeId(caster)=='E00D' or GetUnitTypeId(caster)=='E008' or GetUnitTypeId(caster)=='E00M' or GetUnitTypeId(caster)=='E00O' then
set bj_forLoopAIndex=0
loop
exitwhen bj_forLoopAIndex>5
call UnitRemoveItemFromSlot(caster,bj_forLoopAIndex)
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
call UnitAddItemByIdSwapped('I09I',caster)
else
set bj_forLoopAIndex=0
loop
exitwhen bj_forLoopAIndex>5
call UnitRemoveItemFromSlot(caster,bj_forLoopAIndex)
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
set bj_forLoopAIndex=1
loop
exitwhen bj_forLoopAIndex>2
call UnitAddItemByIdSwapped('I09I',caster)
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
endif
endif
set a=KillNT[ID]/4+150
set KStr[ID]=KStr[ID]+(a-150)
set KAgi[ID]=KAgi[ID]+(a-150)
set KInt[ID]=KInt[ID]+(a-150)
call ModifyHeroStat(bj_HEROSTAT_STR,caster,bj_MODIFYMETHOD_ADD,a)
call ModifyHeroStat(bj_HEROSTAT_AGI,caster,bj_MODIFYMETHOD_ADD,a)
call ModifyHeroStat(bj_HEROSTAT_INT,caster,bj_MODIFYMETHOD_ADD,a)
call SaveReal(udg_hash,h,StringHash("StrUP"),LoadReal(udg_hash,h,StringHash("StrUP"))+0.1)
call SaveReal(udg_hash,h,StringHash("AgiUP"),LoadReal(udg_hash,h,StringHash("AgiUP"))+0.1)
call SaveReal(udg_hash,h,StringHash("IntUP"),LoadReal(udg_hash,h,StringHash("IntUP"))+0.1)
call DisplayTimedTextToForce(bj_FORCE_PLAYER[ID-1],20.00,("|cFF7ED5EAПолучено "+(I2S(a)+" ед. характеристик!")))
set bj_lastCreatedEffect=AddSpecialEffectTarget("war3mapImported\\LightningStrike.mdx",caster,"origin")
call DestroyEffect(bj_lastCreatedEffect)
elseif GetItemTypeId(Item)=='mort' then
set t=CreateTimer()
set ht=GetHandleId(t)
call SaveUnitHandle(udg_hash,ht,1,caster)
call SaveInteger(udg_hash,ht,1,40)
call SaveEffectHandle(udg_hash,ht,2,AddSpecialEffectTarget("war3mapImported\\Ember_Ring_Aura2.mdx",caster,"origin"))
call TimerStart(t,0.2,true,function SingularitySphere_Dmg)
elseif GetItemTypeId(Item)=='I04P' then
set a=30+GetHeroLevel(caster)
call TempStats(caster,0,a,0,0,0,0,PositiveDuration(caster,15))
elseif GetItemTypeId(Item)=='I04O' then
set a=30+GetHeroLevel(caster)
call TempStats(caster,0,0,a,0,0,0,PositiveDuration(caster,15))
elseif GetItemTypeId(Item)=='I04Q' then
set a=30+GetHeroLevel(caster)
call TempStats(caster,a,0,0,0,0,0,PositiveDuration(caster,15))
elseif GetItemTypeId(GetManipulatedItem())=='I09F' then
set a=0
set b=0
set c=0
set WinterFruit[ID]=WinterFruit[ID]+1
if GetHeroStr(caster,false)<=GetHeroAgi(caster,false)then
if GetHeroStr(caster,false)<=GetHeroInt(caster,false)then
set a=30
call DisplayTimedTextToForce(bj_FORCE_PLAYER[ID-1],20.00,"|cFFFFDC00Вы получили "+I2S(a)+" силы!")
else
set c=30
call DisplayTimedTextToForce(bj_FORCE_PLAYER[ID-1],20.00,"|cFFFFDC00Вы получили "+I2S(c)+" разума!")
endif
else
if GetHeroAgi(caster,false)<=GetHeroInt(caster,false)then
set b=30
call DisplayTimedTextToForce(bj_FORCE_PLAYER[ID-1],20.00,"|cFFFFDC00Вы получили "+I2S(b)+" ловкости!")
else
set c=30
call DisplayTimedTextToForce(bj_FORCE_PLAYER[ID-1],20.00,"|cFFFFDC00Вы получили "+I2S(c)+" разума!")
endif
endif
call SetHeroStr(caster,GetHeroStr(caster,false)+a,true)
call SetHeroAgi(caster,GetHeroAgi(caster,false)+b,true)
call SetHeroInt(caster,GetHeroInt(caster,false)+c,true)
call RemoveItem(GetManipulatedItem())
elseif GetItemTypeId(Item)=='I0B5' then
call Func_MageFruit(caster,true)
call RemoveItem(Item)
elseif GetItemTypeId(GetManipulatedItem())=='I0AY' then
if GetHeroLevel(caster)==70 then
call DisplayTimedTextToForce(bj_FORCE_PLAYER[ID-1],15.00,"|cFFFFDC00У вас уже 70 уровень")
elseif GetHeroLevel(caster)<30 then
call DisplayTimedTextToForce(bj_FORCE_PLAYER[ID-1],15.00,"|cFFFFDC00Необходим 30 уровень|r")
else
if GetUnitTypeId(caster)=='Emoo' then
call UnitAddAbility(caster,'A0YZ')
call SaveReal(udg_hash,h,StringHash("RangeSplash"),0.12)
endif
if GetUnitAbilityLevel(caster,'A0M5')>0 then
call SetUnitAbilityLevel(GetTriggerUnit(),'A0M5',3)
endif
if GetUnitTypeId(caster)=='H02T' or GetUnitTypeId(caster)=='H000' or GetUnitTypeId(caster)=='H04O' or GetUnitTypeId(caster)=='H04Q' then
set udg_HeroGold[ID]=udg_HeroGold[ID]+0.4
set udg_HeroGoldMax[ID]=udg_HeroGoldMax[ID]+0.4
if GetUnitTypeId(caster)=='H04O' or GetUnitTypeId(caster)=='H04Q' then
set s__Units_AllDmg[sUnit[iuh]]=s__Units_AllDmg[sUnit[iuh]]+2000
endif
endif
call Reactor(caster)
set udg_ReactorAganim[ID]=true
call RemoveItem(GetManipulatedItem())
endif
elseif GetItemTypeId(Item)=='I0EL' then
call SetUnitMoveSpeed(caster,522.)
set t=CreateTimer()
set ht=GetHandleId(t)
call SaveUnitHandle(udg_hash,ht,0,caster)
call SaveInteger(udg_hash,ht,1,30)
call TimerStart(t,1.,true,function Trig_UseItemJass_EnergyDrink)
elseif GetItemTypeId(Item)=='I0BX' then
set t=CreateTimer()
set ht=GetHandleId(t)
call SaveUnitHandle(udg_hash,ht,0,caster)
call SaveReal(udg_hash,ht,1,8.)
call TimerStart(t,0.5,true,function UseItemJass_ScaleArmor)
elseif GetItemTypeId(Item)=='I0F1' then
set dmg=0.16*GetUnitState(caster,UNIT_STATE_MAX_LIFE)
set udg_ReflectDmg[ID]=udg_ReflectDmg[ID]+dmg
set t=CreateTimer()
set ht=GetHandleId(t)
call SaveInteger(udg_hash,ht,1,ID)
call SaveReal(udg_hash,ht,0,dmg)
call TimerStart(t,8,false,function PerfectCire)
elseif GetItemTypeId(Item)=='I02U' then
set b=LoadInteger(udg_hash,h,StringHash("StaffGold1"))
if UnitHasItemOfTypeBJ(caster,'I0E9')and b>0 then
set u=udg_Hero[LoadInteger(udg_hash,h,StringHash("StaffGoldID"))+1]
if u==null then
set u=caster
endif
else
set u=caster
endif
set a=GetUnitLevel(caster)/2
set b=GetUnitLevel(caster)/2
set c=GetUnitLevel(caster)/2
if LoadStr(udg_hash,h,2)=="Str" then
set a=R2I(0.25*GetHeroStr(u,false))
else
if LoadStr(udg_hash,h,2)=="Agi" then
set b=R2I(0.25*GetHeroAgi(u,false))
else
set c=R2I(0.25*GetHeroInt(u,false))
endif
endif
call TempStats(u,a,b,c,0,0,0,PositiveDuration(caster,18))
elseif GetItemTypeId(GetManipulatedItem())=='I08X' then
set a=2*GetHeroStr(caster,false)
set s__Heroes_TempStr[sHero[ihh]]=s__Heroes_TempStr[sHero[ihh]]+a
call F_Stats(caster)
set t=CreateTimer()
set ht=GetHandleId(t)
call SaveUnitHandle(udg_hash,ht,0,caster)
call SaveInteger(udg_hash,ht,1,a)
call TimerStart(t,12.,false,function Trig_UseItemJass_LGA)
elseif GetItemTypeId(GetManipulatedItem())=='I0E6' then
set s__Units_AllBlock[sUnit[iuh]]=s__Units_AllBlock[sUnit[iuh]]+3000
set s__Units_MageBlock[sUnit[iuh]]=s__Units_MageBlock[sUnit[iuh]]+3000
set bj_lastCreatedEffect=AddSpecialEffectTarget("Abilities\\Spells\\Orc\\Voodoo\\VoodooAuraTarget.mdl",caster,"chest")
set t=CreateTimer()
set ht=GetHandleId(t)
call SaveUnitHandle(udg_hash,ht,0,GetTriggerUnit())
call SaveEffectHandle(udg_hash,ht,1,bj_lastCreatedEffect)
call TimerStart(t,12.,false,function Trig_UseItemJass_GladiatorShield)
elseif GetItemTypeId(GetManipulatedItem())=='I0B7' then
set x=GetUnitX(caster)
set y=GetUnitY(caster)
set dmg=250+.75*GetHeroInt(caster,true)
call SeekMinDummys()
set bj_forLoopAIndex=1
loop
exitwhen bj_forLoopAIndex>6
set u=CreateUnit(Player(ID-1),'h05G',x,y,0.)
call UnitAddAbility(u,'A0W8')
set x1=x+150.*Cos(60*bj_forLoopAIndex*bj_DEGTORAD)
set y1=y+150.*Sin(60*bj_forLoopAIndex*bj_DEGTORAD)
set a=SeekFreeDummysMin(u,GetHandleId(u))
set s__Dummys_dmg[sDummy[a]]=dmg
call IssuePointOrder(u,"carrionswarm",x1,y1)
call UnitApplyTimedLife(u,'BTLF',2.5)
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
elseif GetItemTypeId(GetManipulatedItem())=='I05I' then
set x=GetUnitX(caster)
set y=GetUnitY(caster)
set bj_forLoopAIndex=1
loop
exitwhen bj_forLoopAIndex>10
set x1=x+300.*Cos(36*bj_forLoopAIndex*bj_DEGTORAD)
set y1=y+300.*Sin(36*bj_forLoopAIndex*bj_DEGTORAD)
call DestroyEffect(AddSpecialEffect("Abilities\\Spells\\NightElf\\ReviveNightElf\\ReviveNightElf.mdl",x1,y1))
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
call SetPlayerHandicapBJ(GetOwningPlayer(caster),150.00)
call SaveReal(udg_hash,h,StringHash("SummonHP"),0.2+LoadReal(udg_hash,h,StringHash("SummonHP")))
elseif GetItemTypeId(GetManipulatedItem())=='I0BO' then
set x=GetUnitX(caster)
set y=GetUnitY(caster)
set bj_forLoopAIndex=1
loop
exitwhen bj_forLoopAIndex>8
set x1=x+275.*Cos(45*bj_forLoopAIndex*bj_DEGTORAD)
set y1=y+275.*Sin(45*bj_forLoopAIndex*bj_DEGTORAD)
set bj_lastCreatedEffect=AddSpecialEffect("Abilities\\Spells\\Undead\\AnimateDead\\AnimateDeadTarget.mdl",x,y)
call DestroyEffect(bj_lastCreatedEffect)
set u=CreateUnit(GetOwningPlayer(caster),'u00X',x1,y1,bj_forLoopAIndex*30.)
call UnitAddAbility(u,'A007')
call UnitAddAbility(u,'A13N')
call UnitAddAbility(u,'A0DC')
call UnitAddAbility(u,'A026')
call UnitAddAbility(u,'A129')
call UnitAddAbility(u,'A12I')
call UnitAddItemById(u,'I0CW')
call SummonStats(true,R2I(6*GetHeroStr(caster,true)+7*GetHeroInt(caster,true)),R2I(0.45*GetHeroInt(caster,true)),u,caster)
call UnitRemoveAbility(u,'A007')
call UnitApplyTimedLife(u,'BTLF',35.)
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
elseif GetItemTypeId(GetManipulatedItem())=='I07D' then
set p2=GetUnitLoc(caster)
set bj_forLoopAIndex=1
set bj_forLoopAIndexEnd=12
loop
exitwhen bj_forLoopAIndex>bj_forLoopAIndexEnd
set p=PolarProjectionBJ(p2,400.00,(bj_forLoopAIndex*30.00))
set bj_lastCreatedEffect=AddSpecialEffectLoc("Abilities\\Spells\\Human\\HolyBolt\\HolyBoltSpecialArt.mdl",p)
call DestroyEffect(bj_lastCreatedEffect)
set u=CreateUnitAtLoc(GetOwningPlayer(caster),'h007',p,bj_forLoopAIndex*30.)
call SetUnitVertexColorBJ(u,100,100,100,50.00)
call UnitAddAbility(u,'A007')
call SummonStats(true,R2I(6*(GetHeroStr(caster,true)+GetHeroInt(caster,true))),R2I(0.35*GetHeroInt(caster,true)),u,caster)
call UnitRemoveAbility(u,'A007')
call UnitApplyTimedLife(u,'BTLF',45.)
call RemoveLocation(p)
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
call RemoveLocation(p2)
elseif GetItemTypeId(GetManipulatedItem())=='I08R' then
set p2=GetUnitLoc(caster)
set bj_forLoopAIndex=1
loop
exitwhen bj_forLoopAIndex>12
set p=PolarProjectionBJ(p2,400.00,(bj_forLoopAIndex*30.00))
set bj_lastCreatedEffect=AddSpecialEffectLoc("Objects\\Spawnmodels\\NightElf\\EntBirthTarget\\EntBirthTarget.mdl",p)
call DestroyEffect(bj_lastCreatedEffect)
set u=CreateUnitAtLoc(GetOwningPlayer(caster),'e00I',p,bj_forLoopAIndex*30.)
call UnitAddAbility(u,'A007')
call UnitAddAbility(u,'A17O')
call SetUnitAbilityLevel(u,'A17O',GetUnitAbilityLevel(u,'A17O')+15)
call SummonStats(false,R2I(3500),R2I(300),u,caster)
call SummonStats(true,8*(GetHeroStr(caster,true)+GetHeroInt(caster,true)),R2I(0.4*GetHeroInt(caster,true)),u,caster)
call UnitRemoveAbility(u,'A007')
call UnitApplyTimedLife(u,'BTLF',40.)
call RemoveLocation(p)
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
call RemoveLocation(p2)
elseif GetItemTypeId(GetManipulatedItem())=='I095' then
set a=R2I(1.5*GetHeroInt(caster,true))
set b=40*(GetHeroStr(caster,true)+GetHeroInt(caster,true))
set x=GetUnitX(caster)+250*Cos((GetUnitFacing(caster)+90)*bj_DEGTORAD)
set y=GetUnitY(caster)+250*Sin((GetUnitFacing(caster)+90)*bj_DEGTORAD)
set u=CreateUnit(GetOwningPlayer(caster),'n060',x,y,GetUnitFacing(caster))
call UnitAddAbility(u,'A007')
call SummonStats(true,b,a,u,caster)
call UnitRemoveAbility(u,'A007')
call UnitApplyTimedLife(u,'BTLF',35.)
set x=GetUnitX(caster)+250*Cos((GetUnitFacing(caster)+270)*bj_DEGTORAD)
set y=GetUnitY(caster)+250*Sin((GetUnitFacing(caster)+270)*bj_DEGTORAD)
set u=CreateUnit(GetOwningPlayer(caster),'n060',x,y,GetUnitFacing(caster))
call UnitAddAbility(u,'A007')
call SummonStats(true,b,a,u,caster)
call UnitRemoveAbility(u,'A007')
call UnitApplyTimedLife(u,'BTLF',35.)
elseif GetItemTypeId(Item)=='I0BA' then
set x=0.6*GetHeroAgi(caster,false)
set y=0
set bj_forLoopAIndex=0
loop
exitwhen bj_forLoopAIndex>=6
if GetItemTypeId(UnitItemInSlot(caster,bj_forLoopAIndex))=='I0BA' then
set y=y+1
endif
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
set y=y-1
if y>0 then
set x=x+(y*0.3*GetHeroAgi(caster,false))
endif
call TempStats(caster,0,R2I(x),0,0,0,0,PositiveDuration(caster,15))
elseif GetItemTypeId(Item)=='I0B3' then
set x=0.6*GetHeroInt(caster,false)
set y=0
set bj_forLoopAIndex=0
loop
exitwhen bj_forLoopAIndex>=6
if GetItemTypeId(UnitItemInSlot(caster,bj_forLoopAIndex))=='I0B3' then
set y=y+1
endif
set bj_forLoopAIndex=bj_forLoopAIndex+1
endloop
set y=y-1
if y>0 then
set x=x+(y*0.3*GetHeroInt(caster,false))
endif
call TempStats(caster,0,0,R2I(x),0,0,0,PositiveDuration(caster,15))
elseif GetItemTypeId(Item)=='I08P' then
call F_DeathBelt(caster)
elseif GetItemTypeId(Item)=='I0EC' then
set x=GetUnitX(caster)
set y=GetUnitY(caster)
set bj_lastCreatedEffect=AddSpecialEffect("Abilities\\Spells\\Other\\Doom\\DoomDeath.mdl",x,y)
call DestroyEffect(bj_lastCreatedEffect)
call GroupEnumUnitsInRange(g,x,y,400.,null)
set dmg=1.5*GetHeroStr(caster,true)
set dmg=2.5*dmg
loop
set u=FirstOfGroup(g)
exitwhen u==null
if UnitAlive(u)and IsUnitEnemy(u,GetOwningPlayer(caster))then
call UnitDamageTarget(caster,u,dmg,false,false,ATTACK_TYPE_NORMAL,DAMAGE_TYPE_MAGIC,WEAPON_TYPE_AXE_MEDIUM_CHOP)
call UnitDamageTarget(caster,u,dmg,false,false,ATTACK_TYPE_CHAOS,DAMAGE_TYPE_NORMAL,WEAPON_TYPE_AXE_MEDIUM_CHOP)
endif
call GroupRemoveUnit(g,u)
endloop
elseif GetItemTypeId(Item)=='I0B2' then
if LoadStr(udg_hash,h,2)=="Str" then
set dmg=GetHeroStr(caster,true)
else
if LoadStr(udg_hash,h,2)=="Agi" then
set dmg=GetHeroAgi(caster,true)
else
set dmg=GetHeroInt(caster,true)
endif
endif
set dmg=(0.4*(dmg+s__Heroes_BaseDmg[sHero[ihh]]))*LoadReal(udg_hash,h,4)
call TempStats(caster,0,0,0,R2I(dmg),0,0,PositiveDuration(caster,10))
elseif GetItemTypeId(Item)=='I09U' then
if LoadStr(udg_hash,h,2)=="Str" then
set dmg=GetHeroStr(caster,true)
else
if LoadStr(udg_hash,h,2)=="Agi" then
set dmg=GetHeroAgi(caster,true)
else
set dmg=GetHeroInt(caster,true)
endif
endif
call TempStats(caster,0,0,0,R2I(dmg),0,0,PositiveDuration(caster,15))
elseif GetItemTypeId(Item)=='I00O' then
call TempStats(caster,R2I(150+0.3*GetHeroStr(caster,true)),R2I(150+0.3*GetHeroAgi(caster,true)),R2I(150+0.3*GetHeroInt(caster,true)),0,0,0,PositiveDuration(caster,16))
elseif GetItemTypeId(Item)=='I04C' then
call SetUnitState(caster,UNIT_STATE_MANA,GetUnitState(caster,UNIT_STATE_MAX_MANA))
set bj_lastCreatedEffect=AddSpecialEffectTarget("Abilities\\Spells\\Undead\\ReplenishMana\\ReplenishManaCasterOverhead.mdl",caster,"origin")
call DestroyEffect(bj_lastCreatedEffect)
elseif GetItemTypeId(Item)=='I0EF' then
call SetUnitState(caster,UNIT_STATE_MANA,GetUnitState(caster,UNIT_STATE_MAX_MANA))
set bj_lastCreatedEffect=AddSpecialEffectTarget("Abilities\\Spells\\Undead\\ReplenishMana\\ReplenishManaCasterOverhead.mdl",caster,"origin")
call DestroyEffect(bj_lastCreatedEffect)
elseif GetItemTypeId(GetManipulatedItem())=='I05Y' then
set x=GetUnitX(caster)
set y=GetUnitY(caster)
call GroupEnumUnitsInRange(g,x,y,600.,null)
set dmg=2.5*(GetHeroStr(caster,true)+GetHeroAgi(caster,true)+GetHeroInt(caster,true))
loop
set u=FirstOfGroup(g)
exitwhen u==null
if UnitAlive(u)and IsUnitEnemy(u,GetOwningPlayer(caster))then
call UnitDamageTarget(caster,u,dmg,false,false,ATTACK_TYPE_NORMAL,DAMAGE_TYPE_MAGIC,WEAPON_TYPE_AXE_MEDIUM_CHOP)
endif
call GroupRemoveUnit(g,u)
endloop
elseif GetItemTypeId(GetManipulatedItem())=='I080' then
set x=GetUnitX(caster)
set y=GetUnitY(caster)
set gt=CreateGroup()
call GroupEnumUnitsInRange(g,x,y,1200.,null)
set dmg=4000.+1.5*GetHeroStr(caster,true)
set a=0
loop
set u=FirstOfGroup(g)
exitwhen u==null
if UnitAlive(u)and IsUnitAlly(u,GetOwningPlayer(caster))then
call GroupAddUnit(gt,u)
endif
call GroupRemoveUnit(g,u)
endloop
set t=CreateTimer()
set ht=GetHandleId(t)
call SaveGroupHandle(udg_hash,ht,0,gt)
call SaveInteger(udg_hash,ht,1,R2I(10/0.25))
call SaveReal(udg_hash,ht,2,(dmg*0.25)/10)
call SaveUnitHandle(udg_hash,ht,3,caster)
call TimerStart(t,0.25,true,function Trig_UseItemJass_HelpStaff)
elseif GetItemTypeId(GetManipulatedItem())=='I0EP' then
call Immortal(caster,4)
elseif GetItemTypeId(GetManipulatedItem())=='I0EI' then
call Heal(true,3.*GetHeroAgi(caster,true),caster,caster)
call TempStats(caster,0,R2I(0.3*GetHeroAgi(caster,false)),0,0,0,0,PositiveDuration(caster,15))
elseif GetItemTypeId(GetManipulatedItem())=='I09Z' then
set a=GetHeroStr(caster,false)/4
set b=GetHeroAgi(caster,false)/4
set c=GetHeroInt(caster,false)/4
call TempStats(caster,a,b,c,0,0,0,PositiveDuration(caster,25))
elseif GetItemTypeId(Item)=='I0AE' then
call RemoveItem(Item)
call UnitAddItemByIdSwapped('I0AF',caster)
elseif GetItemTypeId(Item)=='I0AF' then
call RemoveItem(GetManipulatedItem())
call UnitAddItemByIdSwapped('I0AE',caster)
elseif GetItemTypeId(Item)=='I08O' then
call RemoveItem(Item)
call UnitAddItemByIdSwapped('I0C9',caster)
elseif GetItemTypeId(Item)=='I0C9' then
call RemoveItem(GetManipulatedItem())
call UnitAddItemByIdSwapped('I08O',caster)
elseif GetItemTypeId(Item)=='I0D9' then
call RemoveItem(GetManipulatedItem())
call UnitAddItemByIdSwapped('I08G',caster)
elseif GetItemTypeId(Item)=='I08G' then
call RemoveItem(Item)
call UnitAddItemByIdSwapped('I0D9',caster)
elseif GetItemTypeId(Item)=='I09G' then
call RemoveItem(Item)
call UnitAddItemByIdSwapped('I0EH',caster)
elseif GetItemTypeId(Item)=='I0EH' then
call RemoveItem(Item)
call UnitAddItemByIdSwapped('I09G',caster)
elseif GetItemTypeId(Item)=='I0EX' or GetItemTypeId(Item)=='I0EY' or GetItemTypeId(Item)=='I0F2' then
if GetItemTypeId(Item)=='I0EY' then
set dmg=500+4*highstat
set x=PositiveDuration(caster,45)
elseif GetItemTypeId(Item)=='I0F2' then
set dmg=400+2*highstat
set x=PositiveDuration(caster,15)
else
set dmg=400+highstat
set x=PositiveDuration(caster,15)
endif
set dmg=F_Barrier(caster,dmg)
set s__Units_Bar[sUnit[iuh]]=s__Units_Bar[sUnit[iuh]]-s__Heroes_BarAmRin[sHero[ihh]]+dmg
set s__Heroes_BarAmRin[sHero[ihh]]=dmg
if s__Units_BarE[sUnit[iuh]]==null then
set s__Units_BarE[sUnit[iuh]]=AddSpecialEffectTarget("war3mapImported\\MagicShield.mdx",caster,"origin")
endif
set y=LoadReal(udg_hash,h,StringHash("AmuRinSec"))
call SaveReal(udg_hash,h,StringHash("AmuRinSec"),x)
if y<0.1 then
set t=CreateTimer()
set ht=GetHandleId(t)
call SaveUnitHandle(udg_hash,ht,0,caster)
call TimerStart(t,.25,true,function F_AmuletRin)
endif
elseif GetItemTypeId(Item)=='I08Y' and pick_item[ID]==false then
set a=GetRandomInt(1,9)
set c=GetRandomInt(1,8)
if a==1 then
set a='I00J'
elseif a==2 then
set a='I0A0'
elseif a==3 then
set a='I08Z'
elseif a==4 then
set a='I090'
elseif a==5 then
set a='I093'
elseif a==6 then
set a='I09W'
elseif a==7 then
set a='I09Z'
elseif a==8 then
set a='I0EJ'
elseif a==9 then
set a='I08W'
endif
if c==1 then
set c='I095'
elseif c==2 then
set c='I09A'
elseif c==3 then
set c='I09X'
elseif c==4 then
set c='I092'
elseif c==5 then
set c='I091'
elseif c==6 then
set c='I09D'
elseif c==7 then
set c='I0DA'
elseif c==8 then
set c='I0EK'
endif
call Pick_Item(ID,a,c,0,0,0,0,false)
call RemoveItem(Item)
elseif GetItemTypeId(Item)=='I0A2' and pick_item[ID]==false then
set a=GetRandomInt(1,4)
set b=GetRandomInt(1,4)
set c=GetRandomInt(1,4)
set d=GetRandomInt(1,5)
if a==1 then
set a='I00J'
elseif a==2 then
set a='I0A0'
elseif a==3 then
set a='I090'
elseif a==4 then
set a='I08Z'
else
set a=0
endif
if b==1 then
set b='I09W'
elseif b==2 then
set b='I091'
elseif b==3 then
set b='I0DA'
elseif b==4 then
set b='I0EJ'
else
set b=0
endif
if c==1 then
set c='I095'
elseif c==2 then
set c='I09A'
elseif c==3 then
set c='I09X'
elseif c==4 then
set c='I092'
else
set c=0
endif
if d==1 then
set d='I093'
elseif d==2 then
set d='I09D'
elseif d==3 then
set d='I09Z'
elseif d==4 then
set d='I0EK'
elseif d==5 then
set d='I08W'
else
set d=0
endif
call Pick_Item(ID,a,b,c,d,0,0,false)
call RemoveItem(Item)
endif
call DestroyGroup(g)
set caster=null
set Item=null
set u=null
set t=null
set p=null
set p2=null
set g=null
set gt=null
endfunction

```

### 风险函数 #10 (风险评分: 10)
```jass
function Modificator takes unit hero,unit attack,unit target returns nothing
local integer a=0
local integer b
local integer ID=GetPlayerId(GetOwningPlayer(attack))+1
local integer h=GetHandleId(hero)
local integer ha=GetHandleId(attack)
local integer i
local integer i2
local boolean array HaveIt
local timer t
local integer ht
local real x
local real y
local real xa=GetUnitX(attack)
local real ya=GetUnitY(attack)
local real xt=GetUnitX(target)
local real yt=GetUnitY(target)
local real damage
local real dmg
local group g=CreateGroup()
local group g2=CreateGroup()
local unit u
local real bonus=1+LoadReal(udg_hash,h,StringHash("Modificator"))
local real Attacks=Summ_Attack(hero)
local string str
local integer highstat
local integer ids=ReturnTypeHeroId(GetHandleId(hero))
local real CD=s__Heroes_ModCD[sHero[ids]]
if target !=null then
if CD<=0 then
set CD=1
endif
if GetHeroStr(hero,true)>=GetHeroAgi(hero,true)then
if GetHeroStr(hero,true)>=GetHeroInt(hero,true)then
set highstat=GetHeroStr(hero,true)
else
set highstat=GetHeroInt(hero,true)
endif
else
if GetHeroAgi(hero,true)>=GetHeroInt(hero,true)then
set highstat=GetHeroAgi(hero,true)
else
set highstat=GetHeroInt(hero,true)
endif
endif
set udg_VampirHealTarget[ID]=target
set HaveIt[0]=false
set HaveIt[1]=false
set HaveIt[2]=false
set HaveIt[3]=false
set HaveIt[4]=false
set HaveIt[5]=false
set HaveIt[6]=false
set HaveIt[7]=false
set a=0
loop
exitwhen a>5
set b=GetItemTypeId(UnitItemInSlot(hero,a))
if b=='I06O' then
set HaveIt[0]=true
endif
if b=='I051' then
set HaveIt[1]=true
endif
if b=='I0DT' then
set HaveIt[2]=true
endif
if b=='I0BV' then
set HaveIt[3]=true
endif
if b=='I0AE' then
set HaveIt[4]=true
endif
if b=='I0AF' then
set HaveIt[5]=true
endif
if b=='I08Q' then
set HaveIt[6]=true
endif
if b=='I0BB' then
set HaveIt[7]=true
endif
set a=a+1
endloop
if HaveIt[0]then
set udg_DragonSlayerItem[ID]=udg_DragonSlayerItem[ID]+1
if udg_DragonSlayerItem[ID]>=3 then
set damage=(700+0.7*GetHeroInt(hero,true))*bonus
set udg_DragonSlayerItem[ID]=0
call UnitDamageTarget(attack,target,damage,false,false,ATTACK_TYPE_NORMAL,DAMAGE_TYPE_MAGIC,WEAPON_TYPE_METAL_LIGHT_CHOP)
set udg_Drop2=ID-1
call GroupEnumUnitsInRange(g,xt,yt,275.,Bool_Filter_ID)
call GroupRemoveUnit(g,target)
loop
set u=FirstOfGroup(g)
exitwhen u==null
call UnitDamageTarget(attack,u,damage,false,false,ATTACK_TYPE_NORMAL,DAMAGE_TYPE_MAGIC,WEAPON_TYPE_METAL_LIGHT_CHOP)
call GroupRemoveUnit(g,u)
endloop
set bj_lastCreatedEffect=AddSpecialEffect("Abilities\\Spells\\Other\\Doom\\DoomDeath.mdl",xt,yt)
call DestroyEffect(bj_lastCreatedEffect)
else
endif
endif
if HaveIt[1]then
if GetRandomInt(1,5)==1 then
set damage=60.
if LoadStr(udg_hash,h,2)=="Str" then
set damage=damage+0.4*GetHeroStr(hero,true)
else
if LoadStr(udg_hash,h,2)=="Agi" then
set damage=damage+0.4*GetHeroAgi(hero,true)
else
set damage=damage+0.4*GetHeroInt(hero,true)
endif
endif
set damage=damage*bonus/2
set bj_lastCreatedEffect=AddSpecialEffect("Objects\\Spawnmodels\\Orc\\Orcblood\\BattrollBlood.mdl",xt,yt)
call DestroyEffect(bj_lastCreatedEffect)
call UnitDamageTarget(attack,target,damage,false,false,ATTACK_TYPE_NORMAL,DAMAGE_TYPE_MAGIC,WEAPON_TYPE_AXE_MEDIUM_CHOP)
call GroupDamage(xt,yt,225.,attack,false,damage,ATTACK_TYPE_NORMAL,DAMAGE_TYPE_MAGIC)
endif
endif
if HaveIt[2]then
set udg_DemolitronItem=udg_DemolitronItem+1
if udg_DemolitronItem>=6 then
set udg_DemolitronItem=0
set damage=(1000.+4.*GetHeroStr(hero,true))*bonus
call UnitDamageTarget(attack,target,damage,false,false,ATTACK_TYPE_NORMAL,DAMAGE_TYPE_MAGIC,WEAPON_TYPE_METAL_LIGHT_CHOP)
set udg_Drop2=ID-1
call GroupEnumUnitsInRange(g,xt,yt,325.,Bool_Filter_ID)
call GroupRemoveUnit(g,target)
set damage=0.6*damage
loop
set u=FirstOfGroup(g)
exitwhen u==null
call UnitDamageTarget(attack,u,damage,false,false,ATTACK_TYPE_NORMAL,DAMAGE_TYPE_MAGIC,WEAPON_TYPE_METAL_LIGHT_CHOP)
call GroupRemoveUnit(g,u)
endloop
set bj_lastCreatedEffect=AddSpecialEffect("Abilities\\Spells\\Other\\Doom\\DoomDeath.mdl",xt,yt)
call DestroyEffect(bj_lastCreatedEffect)
set bj_lastCreatedEffect=AddSpecialEffect("Objects\\Spawnmodels\\Other\\NeutralBuildingExplosion\\NeutralBuildingExplosion.mdl",xt,yt)
call DestroyEffect(bj_lastCreatedEffect)
endif
endif
if HaveIt[3]then
if GetRandomInt(1,2)==1 then
set damage=(250+highstat*0.3)*bonus
call SetUnitState(attack,UNIT_STATE_LIFE,GetUnitState(attack,UNIT_STATE_LIFE)+0.5*damage)
call UnitDamageTarget(attack,target,damage,false,false,ATTACK_TYPE_NORMAL,DAMAGE_TYPE_MAGIC,WEAPON_TYPE_METAL_LIGHT_CHOP)
set bj_lastCreatedEffect=AddSpecialEffectTarget("Abilities\\Spells\\Other\\Stampede\\StampedeMissileDeath.mdl",target,"origin")
call DestroyEffect(bj_lastCreatedEffect)
endif
endif
if HaveIt[4]then
if GetRandomInt(1,10)<=4 then
set damage=(1.25*GetHeroAgi(hero,true))*bonus
set udg_dmg=damage*0.5
set damage=damage*0.5
set udg_Drop2=ID-1
call GroupEnumUnitsInRange(g,xa,ya,500.,Bool_Filter_ID)
loop
set u=FirstOfGroup(g)
exitwhen u==null
call UnitDamageTarget(attack,u,udg_dmg,false,false,ATTACK_TYPE_NORMAL,DAMAGE_TYPE_MAGIC,WEAPON_TYPE_METAL_LIGHT_CHOP)
call UnitDamageTarget(attack,u,damage,false,false,ATTACK_TYPE_CHAOS,DAMAGE_TYPE_NORMAL,WEAPON_TYPE_METAL_LIGHT_CHOP)
call GroupRemoveUnit(g,u)
endloop
set bj_lastCreatedEffect=AddSpecialEffect("Objects\\Spawnmodels\\Human\\HumanBlood\\BloodElfSpellThiefBlood.mdl",xa,ya)
call DestroyEffect(bj_lastCreatedEffect)
endif
endif
if HaveIt[5]then
set dmg=(1.25*GetHeroAgi(hero,true))*bonus
call UnitDamageTarget(attack,target,0.5*dmg,false,false,ATTACK_TYPE_NORMAL,DAMAGE_TYPE_MAGIC,WEAPON_TYPE_METAL_LIGHT_CHOP)
call UnitDamageTarget(attack,target,0.5*dmg,false,false,ATTACK_TYPE_CHAOS,DAMAGE_TYPE_NORMAL,WEAPON_TYPE_METAL_LIGHT_CHOP)
set bj_lastCreatedEffect=AddSpecialEffectTarget("Objects\\Spawnmodels\\Human\\HumanBlood\\BloodElfSpellThiefBlood.mdl",attack,"origin")
call DestroyEffect(bj_lastCreatedEffect)
endif
if HaveIt[6]then
if GetUnitLevel(target)>=30 then
set a=25
else
set a=10+GetUnitLevel(target)/2
endif
if GetRandomInt(1,100)<=a then
set damage=.4*highstat*bonus
call GroupDamage(xt,yt,175.,attack,false,damage,ATTACK_TYPE_NORMAL,DAMAGE_TYPE_MAGIC)
endif
endif
if HaveIt[7]then
set a=GetPlayerState(GetOwningPlayer(attack),PLAYER_STATE_RESOURCE_GOLD)
if a>30000 then
set damage=(1200+0.024*(a-30000))*bonus
set dmg=(900+0.018*(a-30000))*bonus
else
set damage=(0.04*a)*bonus
set dmg=(0.03*a)*bonus
endif
if LoadBoolean(udg_hash,h,StringHash("SetMidas"))then
set damage=2.*damage
set dmg=2.*dmg
endif
call UnitDamageTarget(attack,target,damage,false,true,ATTACK_TYPE_CHAOS,DAMAGE_TYPE_NORMAL,WEAPON_TYPE_METAL_LIGHT_CHOP)
if GetRandomInt(1,8)==1 then
set udg_Drop2=ID-1
call GroupEnumUnitsInRange(g,xt,yt,250.,Bool_Filter_ID)
loop
set u=FirstOfGroup(g)
exitwhen u==null
call UnitDamageTarget(attack,u,dmg,false,false,ATTACK_TYPE_NORMAL,DAMAGE_TYPE_MAGIC,WEAPON_TYPE_METAL_LIGHT_CHOP)
call GroupRemoveUnit(g,u)
endloop
set bj_lastCreatedEffect=AddSpecialEffectTarget("Abilities\\Spells\\Other\\Incinerate\\IncinerateBuff.mdl",target,"origin")
call DestroyEffect(bj_lastCreatedEffect)
endif
endif
set HaveIt[0]=false
set HaveIt[1]=false
set HaveIt[2]=false
set HaveIt[3]=false
set HaveIt[4]=false
set HaveIt[5]=false
set HaveIt[6]=false
set HaveIt[7]=false
set a=0
loop
exitwhen a>5
set b=GetItemTypeId(UnitItemInSlot(hero,a))
if b=='I07B' then
set HaveIt[0]=true
endif
if b=='I063' then
set HaveIt[1]=true
endif
if b=='I0A0' then
set HaveIt[2]=true
endif
if b=='I04K' then
set HaveIt[3]=true
endif
if b=='I07W' then
set HaveIt[4]=true
endif
if b=='I0BQ' then
set HaveIt[5]=true
endif
if b=='I061' then
set HaveIt[6]=true
endif
if b=='I079' then
set HaveIt[7]=true
endif
set a=a+1
endloop
if HaveIt[0]then
if GetRandomInt(1,10)==2 then
set damage=(480+0.08*GetHeroAgi(hero,true))*bonus
set udg_Drop2=ID-1
call GroupEnumUnitsInRange(g,xa,ya,400.,Bool_Filter_ID)
loop
set u=FirstOfGroup(g)
exitwhen u==null
call UnitDamageTarget(attack,u,damage,false,false,ATTACK_TYPE_CHAOS,DAMAGE_TYPE_UNIVERSAL,WEAPON_TYPE_METAL_LIGHT_CHOP)
set bj_lastCreatedEffect=AddSpecialEffectTarget("Objects\\Spawnmodels\\Orc\\OrcSmallDeathExplode\\OrcSmallDeathExplode.mdl",u,"chest")
call DestroyEffect(bj_lastCreatedEffect)
call GroupRemoveUnit(g,u)
endloop
endif
endif
if HaveIt[1]then
if GetRandomInt(1,4)==1 then
set damage=(600+0.4*GetHeroStr(hero,true))*bonus
set udg_Drop2=ID-1
call GroupEnumUnitsInRange(g,xa,ya,450.00,Bool_Filter_ID)
call RandomUnitFromGroup(3,g)
loop
set u=FirstOfGroup(g)
exitwhen u==null
call UnitDamageTarget(attack,u,damage,false,false,ATTACK_TYPE_CHAOS,DAMAGE_TYPE_NORMAL,WEAPON_TYPE_METAL_LIGHT_CHOP)
set bj_lastCreatedEffect=AddSpecialEffectTarget("Abilities\\Spells\\Other\\Incinerate\\FireLordDeathExplode.mdl",u,"origin")
call DestroyEffect(bj_lastCreatedEffect)
call GroupRemoveUnit(g,u)
endloop
endif
endif
if HaveIt[2]then
if GetRandomInt(1,5)==1 then
set damage=(1600.+2.*GetHeroStr(hero,true))*bonus
set dmg=0.25*damage
set damage=0.75*damage
set y=0.1*GetHeroStr(hero,true)
set x=GetUnitState(attack,UNIT_STATE_LIFE)
if y+1.<x then
call SetUnitState(attack,UNIT_STATE_LIFE,x-y)
else
call SetUnitState(attack,UNIT_STATE_LIFE,1.)
endif
set udg_Drop2=ID-1
call GroupEnumUnitsInRange(g,xa,ya,500.00,Bool_Filter_ID)
call RandomUnitFromGroup(3,g)
call DestroyGroup(udg_ug)
set udg_ug=CreateGroup()
loop
set u=FirstOfGroup(g)
exitwhen u==null
set b=GetPlayerId(GetLocalPlayer())+1
set str="Abilities\\Spells\\Other\\Incinerate\\FireLordDeathExplode.mdl"
if OptEffect[b]then
set str=""
endif
set bj_lastCreatedEffect=AddSpecialEffectTarget(str,u,"chest")
call DestroyEffect(bj_lastCreatedEffect)
set udg_Drop2=ID-1
call GroupEnumUnitsInRange(g2,GetUnitX(u),GetUnitY(u),275.,Bool_Filter_ID_innoG)
call ForGroup(g2,function FG_Filter_ID_innoG)
call GroupClear(g2)
call GroupRemoveUnit(g,u)
endloop
loop
set u=FirstOfGroup(udg_ug)
exitwhen u==null
call UnitDamageTarget(attack,u,damage,false,false,ATTACK_TYPE_CHAOS,DAMAGE_TYPE_NORMAL,WEAPON_TYPE_METAL_LIGHT_CHOP)
call UnitDamageTarget(attack,u,dmg,false,false,ATTACK_TYPE_NORMAL,DAMAGE_TYPE_UNIVERSAL,WEAPON_TYPE_METAL_LIGHT_CHOP)
call GroupRemoveUnit(udg_ug,u)
endloop
endif
endif
if HaveIt[3]then
set damage=(80.+.08*Attacks)*bonus
set udg_Drop2=ID-1
call DestroyEffect(AddSpecialEffectTarget("Abilities\\Spells\\Items\\AIfb\\AIfbTarget.mdl",target,"origin"))
call GroupEnumUnitsInRange(g,xt,yt,250.00,Bool_Filter_ID)
call GroupRemoveUnit(g,target)
loop
set u=FirstOfGroup(g)
exitwhen u==null
call UnitDamageTarget(attack,u,damage,false,false,ATTACK_TYPE_HERO,DAMAGE_TYPE_NORMAL,WEAPON_TYPE_METAL_LIGHT_CHOP)
call GroupRemoveUnit(g,u)
endloop
endif
if HaveIt[4]then
if GetRandomInt(1,100)<=22 then
set damage=(475.+GetHeroStr(hero,true)*0.75)*bonus
set udg_Drop2=ID-1
call GroupEnumUnitsInRange(g,xa,ya,400.00,Bool_Filter_ID)
loop
set u=FirstOfGroup(g)
exitwhen u==null
call UnitDamageTarget(attack,u,damage,false,false,ATTACK_TYPE_NORMAL,DAMAGE_TYPE_MAGIC,WEAPON_TYPE_METAL_LIGHT_CHOP)
call DestroyEffect(AddSpecialEffectTarget("Abilities\\Spells\\Human\\HolyBolt\\HolyBoltSpecialArt.mdl",u,"chest"))
call GroupRemoveUnit(g,u)
endloop
endif
endif
if HaveIt[5]then
if GetRandomInt(1,4)==1 then
set damage=(600+0.4*Attacks)*bonus*Psych_crit(hero,.75,1.25)
set udg_Drop2=ID-1
call GroupEnumUnitsInRange(g,xt,yt,350.00,Bool_Filter_ID)
call RandomUnitFromGroup(8,g)
set a=0
loop
set u=FirstOfGroup(g)
exitwhen u==null
call UnitDamageTarget(attack,u,damage,false,false,ATTACK_TYPE_NORMAL,DAMAGE_TYPE_MAGIC,WEAPON_TYPE_METAL_LIGHT_CHOP)
if UnitAlive(u)and LoadBoolean(udg_hash,ha,StringHash("Musket"))==false then
set a=1
set x=GetUnitX(u)
set y=GetUnitY(u)
set bj_lastCreatedUnit=CreateUnit(GetOwningPlayer(attack),'h051',x,y,270.)
call UnitAddAbility(bj_lastCreatedUnit,'A0XF')
call UnitApplyTimedLife(bj_lastCreatedUnit,'BTLF',1.)
call IssueTargetOrder(bj_lastCreatedUnit,"attack",u)
endif
call GroupRemoveUnit(g,u)
endloop
if a==1 then
call Func_CD(attack,"Musket",3)
endif
endif
endif
if HaveIt[6]then
if GetRandomInt(1,4)==1 then
set damage=(120+.2*highstat)*bonus
set udg_Drop2=ID-1
call GroupEnumUnitsInRange(g,xa,ya,450.00,Bool_Filter_ID)
call RandomUnitFromGroup(3,g)
loop
set u=FirstOfGroup(g)
exitwhen u==null
call UnitDamageTarget(attack,u,damage,false,false,ATTACK_TYPE_CHAOS,DAMAGE_TYPE_NORMAL,WEAPON_TYPE_METAL_LIGHT_CHOP)
set bj_lastCreatedEffect=AddSpecialEffectTarget("Abilities\\Spells\\Other\\Incinerate\\FireLordDeathExplode.mdl",u,"origin")
call DestroyEffect(bj_lastCreatedEffect)
call GroupRemoveUnit(g,u)
endloop
endif
endif
if HaveIt[7]then
set udg_p=GetUnitLoc(target)
set a=1
loop
exitwhen a>6
set udg_point=PolarProjectionBJ(udg_p,GetRandomReal(30.00,100.00),GetRandomDirectionDeg())
call AddSpecialEffectLocBJ(udg_point,"Abilities\\Spells\\Human\\HolyBolt\\HolyBoltSpecialArt.mdl")
call DestroyEffectBJ(GetLastCreatedEffectBJ())
call RemoveLocation(udg_point)
set a=a+1
endloop
set damage=(70+0.1*GetHeroInt(hero,true))*bonus
set udg_Drop2=ID-1
call GroupEnumUnitsInRange(g,xa,ya,230.00,Bool_Filter_ID)
loop
set u=FirstOfGroup(g)
exitwhen u==null
call UnitDamageTarget(attack,u,damage,false,false,ATTACK_TYPE_CHAOS,DAMAGE_TYPE_UNIVERSAL,WEAPON_TYPE_METAL_LIGHT_CHOP)
set bj_lastCreatedEffect=AddSpecialEffectTarget("Abilities\\Spells\\Human\\HolyBolt\\HolyBoltSpecialArt.mdl",u,"chest")
call DestroyEffect(bj_lastCreatedEffect)
call GroupRemoveUnit(g,u)
endloop
call RemoveLocation(udg_p)
endif
set HaveIt[0]=false
set HaveIt[1]=false
set HaveIt[2]=false
set HaveIt[3]=false
set HaveIt[4]=false
set HaveIt[5]=false
set HaveIt[6]=false
set HaveIt[7]=false
set a=0
loop
exitwhen a>5
set b=GetItemTypeId(UnitItemInSlot(hero,a))
if b=='I055' then
set HaveIt[0]=true
endif
if b=='I0AO' then
set HaveIt[1]=true
endif
if b=='I06L' then
set HaveIt[2]=true
endif
if b=='I0AQ' then
set HaveIt[3]=true
endif
if b=='I08Z' then
set HaveIt[4]=true
endif
if b=='I0AL' then
set HaveIt[5]=true
endif
if b=='I092' then
set HaveIt[6]=true
endif
if b=='I090' then
set HaveIt[7]=true
endif
set a=a+1
endloop
if HaveIt[0]then
if GetRandomInt(1,5)==1 then
set dmg=(140+0.1*Attacks)*bonus
set bj_lastCreatedUnit=CreateUnit(GetOwningPlayer(attack),'h05G',xa,ya,GetUnitFacing(attack))
set a=SeekFreeDummys(bj_lastCreatedUnit,GetHandleId(bj_lastCreatedUnit))
set s__Dummys_dmg[sDummy[a]]=dmg
call UnitAddAbility(bj_lastCreatedUnit,'A08B')
call UnitApplyTimedLife(bj_lastCreatedUnit,'BTLF',3.)
call IssuePointOrder(bj_lastCreatedUnit,"carrionswarm",xt,yt)
endif
endif
if HaveIt[1]then
if GetRandomInt(1,10)<=3 then
set dmg=(550.+.5*highstat)*bonus
set bj_lastCreatedUnit=CreateUnit(GetOwningPlayer(attack),'h05G',xa,ya,GetUnitFacing(attack))
set a=SeekFreeDummys(bj_lastCreatedUnit,GetHandleId(bj_lastCreatedUnit))
set s__Dummys_dmg[sDummy[a]]=dmg
call UnitAddAbility(bj_lastCreatedUnit,'A0W3')
call UnitApplyTimedLife(bj_lastCreatedUnit,'BTLF',3.)
call IssueTargetOrder(bj_lastCreatedUnit,"frostnova",target)
endif
endif
if HaveIt[2]then
if GetRandomInt(1,5)==1 then
set udg_point=GetUnitLoc(attack)
set dmg=(130+0.08*GetHeroStr(hero,true))*bonus
call SeekMinDummys()
set a=1
loop
exitwhen a>5
set bj_lastCreatedUnit=CreateUnitAtLoc(GetOwningPlayer(attack),'h05G',udg_point,GetUnitFacing(attack))
set i2=SeekFreeDummysMin(bj_lastCreatedUnit,GetHandleId(bj_lastCreatedUnit))
set s__Dummys_dmg[sDummy[i2]]=dmg
call UnitAddAbility(bj_lastCreatedUnit,'A0W8')
set udg_p=PolarProjectionBJ(udg_point,150.00,((GetUnitFacing(attack)+75.00)-(I2R(a)*25.00)))
call IssuePointOrderLoc(bj_lastCreatedUnit,"carrionswarm",udg_p)
call RemoveLocation(udg_p)
call UnitApplyTimedLife(bj_lastCreatedUnit,'BTLF',3.)
set a=a+1
endloop
call RemoveLocation(udg_point)
endif
endif
if HaveIt[3]then
if GetRandomInt(1,5)==1 then
set a=1
set dmg=(500.+0.4*GetHeroAgi(hero,true))*bonus
call SeekMinDummys()
loop
exitwhen a>5
set udg_point=GetUnitLoc(attack)
set bj_lastCreatedUnit=CreateUnitAtLoc(GetOwningPlayer(attack),'h05G',udg_point,GetUnitFacing(attack))
set i2=SeekFreeDummysMin(bj_lastCreatedUnit,GetHandleId(bj_lastCreatedUnit))
set s__Dummys_dmg[sDummy[i2]]=dmg
call UnitAddAbility(bj_lastCreatedUnit,'A0W8')
set udg_p=PolarProjectionBJ(udg_point,150.00,GetUnitFacing(attack)+120.00-a*36.00)
call IssuePointOrderLoc(bj_lastCreatedUnit,"carrionswarm",udg_p)
call RemoveLocation(udg_p)
call UnitApplyTimedLife(bj_lastCreatedUnit,'BTLF',3.)
call RemoveLocation(udg_point)
set a=a+1
endloop
endif
endif
if HaveIt[4]then
if GetRandomInt(1,4)==1 then
if GetRandomInt(1,3)==1 then
set u=target
else
set udg_Drop2=ID-1
call GroupEnumUnitsInRange(g,xa,ya,800.00,Bool_Filter_ID)
call RandomUnitFromGroup(1,g)
set u=FirstOfGroup(g)
endif
set damage=(800.+1.1*GetHeroAgi(hero,true))*bonus
set x=GetUnitX(u)
set y=GetUnitY(u)
set bj_lastCreatedUnit=CreateUnit(GetOwningPlayer(attack),'h01P',x,y,270.)
call UnitApplyTimedLife(bj_lastCreatedUnit,'BTLF',3.00)
call DestroyEffect(AddSpecialEffect("Abilities\\Spells\\Human\\Thunderclap\\ThunderClapCaster.mdl",x,y))
call DestroyEffect(AddSpecialEffect("Doodads\\Cinematic\\Lightningbolt\\Lightningbolt",x,y))
set udg_Drop2=ID-1
call GroupEnumUnitsInRange(g,x,y,500,Bool_Filter_ID)
loop
set u=FirstOfGroup(g)
exitwhen u==null
call UnitDamageTarget(attack,u,damage,false,false,ATTACK_TYPE_NORMAL,DAMAGE_TYPE_MAGIC,WEAPON_TYPE_METAL_LIGHT_CHOP)
call GroupRemoveUnit(g,u)
endloop
endif
endif
if HaveIt[5]and LoadBoolean(udg_hash,ha,StringHash("Kostolom"))==false then
call UnitDamageTarget(attack,target,(GetHeroStr(hero,true)*2)*bonus,false,false,ATTACK_TYPE_CHAOS,DAMAGE_TYPE_NORMAL,WEAPON_TYPE_METAL_LIGHT_CHOP)
call DestroyEffect(AddSpecialEffectTarget("Abilities\\Spells\\Other\\Stampede\\StampedeMissileDeath.mdl",target,"origin"))
call Func_CD(attack,"Kostolom",1.5/CD)
endif
if HaveIt[6]then
if GetRandomInt(1,100)<=25 then
set damage=1000.+GetHeroInt(hero,true)
set bj_lastCreatedEffect=AddSpecialEffect("Abilities\\Spells\\Other\\Incinerate\\FireLordDeathExplode.mdl",xt,yt)
call DestroyEffect(bj_lastCreatedEffect)
set udg_Drop2=ID-1
call GroupEnumUnitsInRange(g,xt,yt,325.00,Bool_Filter_ID)
loop
set u=FirstOfGroup(g)
exitwhen u==null
call UnitDamageTarget(attack,u,damage,false,false,ATTACK_TYPE_NORMAL,DAMAGE_TYPE_MAGIC,WEAPON_TYPE_METAL_LIGHT_CHOP)
call GroupRemoveUnit(g,u)
endloop
call SetUnitState(attack,UNIT_STATE_LIFE,GetUnitState(attack,UNIT_STATE_LIFE)+0.2*damage)
endif
endif
if HaveIt[7]and LoadBoolean(udg_hash,ha,StringHash("Spear Teldrassil"))==false then
call SetUnitState(attack,UNIT_STATE_LIFE,GetUnitState(attack,UNIT_STATE_LIFE)+0.2*GetHeroAgi(hero,true))
set bj_lastCreatedUnit=CreateUnit(GetOwningPlayer(attack),'h051',GetUnitX(target),GetUnitY(target),0)
call UnitApplyTimedLife(bj_lastCreatedUnit,'BTLF',2.)
call UnitAddAbility(bj_lastCreatedUnit,'A0UF')
call IssueTargetOrder(bj_lastCreatedUnit,"attack",target)
set bj_lastCreatedUnit=CreateUnit(GetOwningPlayer(attack),'h051',GetUnitX(target),GetUnitY(target),0)
call UnitApplyTimedLife(bj_lastCreatedUnit,'BTLF',6.5)
call UnitAddAbility(bj_lastCreatedUnit,'AIcb')
call IssueTargetOrder(bj_lastCreatedUnit,"attack",target)
set bj_lastStartedTimer=CreateTimer()
call SaveBoolean(udg_hash,ha,StringHash("Spear Teldrassil"),true)
call SaveInteger(udg_hash,GetHandleId(bj_lastStartedTimer),1,ha)
call TimerStart(bj_lastStartedTimer,1.,false,function Modificator_Teldrassil)
endif
set HaveIt[0]=false
set HaveIt[1]=false
set HaveIt[2]=false
set HaveIt[3]=false
set HaveIt[4]=false
set a=0
loop
exitwhen a>5
set b=GetItemTypeId(UnitItemInSlot(hero,a))
if b=='I014' then
set HaveIt[0]=true
endif
if b=='I0AU' then
set HaveIt[1]=true
endif
if b=='arsh' then
set HaveIt[2]=true
endif
if b=='I0ES' then
set HaveIt[3]=true
endif
if b=='I06K' then
set HaveIt[4]=true
endif
set a=a+1
endloop
if HaveIt[0]then
if IsBoss(target)then
set damage=(0.4*Attacks)*bonus
else
set damage=(0.2*Attacks)*bonus
endif
call UnitDamageTarget(attack,target,damage,false,true,ATTACK_TYPE_CHAOS,DAMAGE_TYPE_NORMAL,WEAPON_TYPE_AXE_MEDIUM_CHOP)
endif
if HaveIt[1]then
set damage=(0.22*Attacks)*bonus*Psych_crit(hero,1.,1.)
call UnitDamageTarget(attack,target,damage,false,true,ATTACK_TYPE_CHAOS,DAMAGE_TYPE_NORMAL,WEAPON_TYPE_AXE_MEDIUM_CHOP)
set udg_Drop2=ID-1
call GroupEnumUnitsInRange(g,xt,yt,275,Bool_Filter_ID)
call GroupRemoveUnit(g,target)
set damage=damage*0.5
loop
set u=FirstOfGroup(g)
exitwhen u==null
call UnitDamageTarget(attack,u,damage,false,false,ATTACK_TYPE_CHAOS,DAMAGE_TYPE_NORMAL,WEAPON_TYPE_METAL_LIGHT_CHOP)
call GroupRemoveUnit(g,u)
endloop
endif
if HaveIt[2]then
set damage=(0.2*Attacks)
set dmg=Psych_crit(hero,1.,1.)
if dmg>bonus then
set damage=damage*dmg
else
set damage=damage*bonus
endif
set udg_Drop2=ID-1
call GroupEnumUnitsInRange(g,xt,yt,275,Bool_Filter_ID)
loop
set u=FirstOfGroup(g)
exitwhen u==null
call UnitDamageTarget(attack,u,damage,false,false,ATTACK_TYPE_CHAOS,DAMAGE_TYPE_NORMAL,WEAPON_TYPE_METAL_LIGHT_CHOP)
call GroupRemoveUnit(g,u)
endloop
endif
if HaveIt[3]then
if not LoadBoolean(udg_hash,ha,StringHash("FatalLight"))then
if LoadStr(udg_hash,h,2)=="Str" then
set damage=GetHeroStr(hero,true)
else
if LoadStr(udg_hash,h,2)=="Agi" then
set damage=GetHeroAgi(hero,true)
else
set damage=GetHeroInt(hero,true)
endif
endif
set damage=(300.+0.8*damage)*bonus
call SetUnitState(attack,UNIT_STATE_LIFE,GetUnitState(attack,UNIT_STATE_LIFE)+0.25*damage)
set x=xa+50*Cos(GetUnitFacing(attack)*bj_DEGTORAD)
set y=ya+50*Sin(GetUnitFacing(attack)*bj_DEGTORAD)
call DestroyEffect(AddSpecialEffect("Abilities\\Spells\\Human\\HolyBolt\\HolyBoltSpecialArt.mdl",x,y))
set udg_Drop2=ID-1
call GroupEnumUnitsInRange(g,x,y,175.,Bool_Filter_ID)
loop
set u=FirstOfGroup(g)
exitwhen u==null
call GroupAddUnit(g2,u)
call GroupRemoveUnit(g,u)
endloop
set x=xa+150*Cos(GetUnitFacing(attack)*bj_DEGTORAD)
set y=ya+150*Sin(GetUnitFacing(attack)*bj_DEGTORAD)
call DestroyEffect(AddSpecialEffect("Abilities\\Spells\\Human\\HolyBolt\\HolyBoltSpecialArt.mdl",x,y))
set udg_Drop2=ID-1
call GroupEnumUnitsInRange(g,x,y,175.,Bool_Filter_ID)
loop
set u=FirstOfGroup(g)
exitwhen u==null
call GroupAddUnit(g2,u)
call GroupRemoveUnit(g,u)
endloop
set x=xa+250*Cos(GetUnitFacing(attack)*bj_DEGTORAD)
set y=ya+250*Sin(GetUnitFacing(attack)*bj_DEGTORAD)
call DestroyEffect(AddSpecialEffect("Abilities\\Spells\\Human\\HolyBolt\\HolyBoltSpecialArt.mdl",x,y))
set udg_Drop2=ID-1
call GroupEnumUnitsInRange(g,x,y,175.,Bool_Filter_ID)
loop
set u=FirstOfGroup(g)
exitwhen u==null
call GroupAddUnit(g2,u)
call GroupRemoveUnit(g,u)
endloop
set x=xa+350*Cos(GetUnitFacing(attack)*bj_DEGTORAD)
set y=ya+350*Sin(GetUnitFacing(attack)*bj_DEGTORAD)
call DestroyEffect(AddSpecialEffect("Abilities\\Spells\\Human\\HolyBolt\\HolyBoltSpecialArt.mdl",x,y))
set udg_Drop2=ID-1
call GroupEnumUnitsInRange(g,x,y,175.,Bool_Filter_ID)
loop
set u=FirstOfGroup(g)
exitwhen u==null
call GroupAddUnit(g2,u)
call GroupRemoveUnit(g,u)
endloop
set x=xa+450*Cos(GetUnitFacing(attack)*bj_DEGTORAD)
set y=ya+450*Sin(GetUnitFacing(attack)*bj_DEGTORAD)
call DestroyEffect(AddSpecialEffect("Abilities\\Spells\\Human\\HolyBolt\\HolyBoltSpecialArt.mdl",x,y))
set udg_Drop2=ID-1
call GroupEnumUnitsInRange(g,x,y,175.,Bool_Filter_ID)
loop
set u=FirstOfGroup(g)
exitwhen u==null
call GroupAddUnit(g2,u)
call GroupRemoveUnit(g,u)
endloop
set x=xa+550*Cos(GetUnitFacing(attack)*bj_DEGTORAD)
set y=ya+550*Sin(GetUnitFacing(attack)*bj_DEGTORAD)
call DestroyEffect(AddSpecialEffect("Abilities\\Spells\\Human\\HolyBolt\\HolyBoltSpecialArt.mdl",x,y))
set udg_Drop2=ID-1
call GroupEnumUnitsInRange(g,x,y,175.,Bool_Filter_ID)
loop
set u=FirstOfGroup(g)
exitwhen u==null
call GroupAddUnit(g2,u)
call GroupRemoveUnit(g,u)
endloop
loop
set u=FirstOfGroup(g2)
exitwhen u==null
call UnitDamageTarget(attack,u,damage,false,false,ATTACK_TYPE_NORMAL,DAMAGE_TYPE_UNIVERSAL,WEAPON_TYPE_METAL_LIGHT_CHOP)
call GroupRemoveUnit(g2,u)
endloop
call Func_CD(attack,"FatalLight",2./CD)
endif
endif
if HaveIt[4]then
set damage=(0.15*Attacks)*bonus
call UnitDamageTarget(attack,target,damage,false,true,ATTACK_TYPE_CHAOS,DAMAGE_TYPE_NORMAL,WEAPON_TYPE_AXE_MEDIUM_CHOP)
endif
set a=0
set i2=0
set b=0
loop
exitwhen a>=6
if GetItemTypeId(UnitItemInSlot(hero,a))=='I0CL' and i2==0 then
set i2=1
endif
if GetItemTypeId(UnitItemInSlot(hero,a))=='I0E0' then
set i2=2
endif
if GetItemTypeId(UnitItemInSlot(hero,a))=='I0E7' then
set b=1
endif
set a=a+1
endloop
if i2>0 then
if LoadBoolean(udg_hash,ha,StringHash("Night"))==false then
set u=CreateUnit(GetOwningPlayer(attack),'h05G',xa,ya,GetUnitFacing(attack))
if i2==2 then
set damage=400+highstat*3
else
set damage=highstat*2
if damage>500 then
set damage=500
else
endif
endif
set damage=damage*bonus
set a=SeekFreeDummys(u,GetHandleId(u))
set s__Dummys_dmg[sDummy[a]]=damage
call UnitAddAbility(u,'A1CN')
call IssuePointOrder(u,"carrionswarm",xt,yt)
call UnitApplyTimedLife(u,'BTLF',4.)
if b==1 then
call Func_CD(attack,"Night",3./CD)
else
call Func_CD(attack,"Night",6./CD)
endif
endif
endif
if GetItemTypeId(UnitItemInSlot(udg_Trophy_build[ID],0))=='rde3' then
if LoadBoolean(udg_hash,ha,StringHash("Fatal shot"))==false then
set damage=(50.+0.5*Attacks)*bonus
set i2=GetUnitLevel(target)
if IsUnitType(target,UNIT_TYPE_HERO)==true or(i2>=15 and ModuloInteger(i2,5)==0)then
set damage=2.*damage
endif
call UnitDamageTarget(attack,target,damage,false,true,ATTACK_TYPE_CHAOS,DAMAGE_TYPE_NORMAL,WEAPON_TYPE_AXE_MEDIUM_CHOP)
call UnitDamageTarget(attack,target,damage,false,false,ATTACK_TYPE_NORMAL,DAMAGE_TYPE_MAGIC,WEAPON_TYPE_AXE_MEDIUM_CHOP)
call Func_CD(attack,"Fatal shot",3./CD)
endif
endif
if GetItemTypeId(UnitItemInSlot(udg_Trophy_build[ID],0))=='rde4' and LoadBoolean(udg_hash,ha,StringHash("Magic Sword"))==false then
if GetUnitState(attack,UNIT_STATE_MAX_MANA)>=3000. then
set damage=60.
call SetUnitState(attack,UNIT_STATE_MANA,GetUnitState(attack,UNIT_STATE_MANA)+30.)
else
set damage=0.02*GetUnitState(attack,UNIT_STATE_MAX_MANA)
call SetUnitState(attack,UNIT_STATE_MANA,GetUnitState(attack,UNIT_STATE_MANA)+0.01*GetUnitState(attack,UNIT_STATE_MAX_MANA))
endif
call UnitDamageTarget(attack,target,damage,false,false,ATTACK_TYPE_NORMAL,DAMAGE_TYPE_MAGIC,WEAPON_TYPE_AXE_MEDIUM_CHOP)
set bj_lastStartedTimer=CreateTimer()
call SaveBoolean(udg_hash,ha,StringHash("Magic Sword"),true)
call SaveInteger(udg_hash,GetHandleId(bj_lastStartedTimer),1,ha)
call TimerStart(bj_lastStartedTimer,1.,false,function Modificator_Magic_Sword)
endif
if GetItemTypeId(UnitItemInSlot(udg_Trophy_build[ID],0))=='ciri' and LoadBoolean(udg_hash,ha,StringHash("Spear Tan"))==false then
set damage=50.+0.5*GetHeroAgi(hero,true)
set bj_lastCreatedUnit=CreateUnit(GetOwningPlayer(attack),'h051',GetUnitX(target),GetUnitY(target),0)
call UnitApplyTimedLife(bj_lastCreatedUnit,'BTLF',2.)
call UnitAddAbility(bj_lastCreatedUnit,'A0UF')
call SetUnitAbilityLevel(bj_lastCreatedUnit,'A0UF',2)
call IssueTargetOrder(bj_lastCreatedUnit,"attack",target)
call SaveBoolean(udg_hash,ha,StringHash("Spear Tan"),true)
set bj_lastStartedTimer=CreateTimer()
set a=GetHandleId(bj_lastStartedTimer)
call SaveUnitHandle(udg_hash,a,0,attack)
call SaveInteger(udg_hash,a,1,3)
call SaveUnitHandle(udg_hash,a,2,target)
call SaveReal(udg_hash,a,3,damage)
call TimerStart(bj_lastStartedTimer,1.,true,function Modificator_Tan)
endif
if GetItemTypeId(UnitItemInSlot(udg_Trophy_build[ID],0))=='hcun' and LoadBoolean(udg_hash,ha,StringHash("Rapire"))==false then
set damage=(0.3*highstat)*bonus
call SetUnitState(attack,UNIT_STATE_LIFE,GetUnitState(attack,UNIT_STATE_LIFE)+0.2*damage)
call UnitDamageTarget(attack,target,damage,false,false,ATTACK_TYPE_CHAOS,DAMAGE_TYPE_UNIVERSAL,WEAPON_TYPE_METAL_LIGHT_CHOP)
call Func_CD(attack,"Rapire",1./CD)
set bj_lastCreatedEffect=AddSpecialEffectTarget("Objects\\Spawnmodels\\Human\\HumanBlood\\HumanBloodMortarTeam.mdl",target,"origin")
call DestroyEffect(bj_lastCreatedEffect)
endif
if GetItemTypeId(UnitItemInSlot(udg_Trophy_build[ID],0))=='jpnt' and LoadBoolean(udg_hash,ha,StringHash("Kolt"))==false then
set damage=(3*Attacks)*bonus*Psych_crit(hero,2.,1.)
call UnitDamageTarget(attack,target,damage,false,false,ATTACK_TYPE_CHAOS,DAMAGE_TYPE_NORMAL,WEAPON_TYPE_METAL_LIGHT_CHOP)
if UnitAlive(target)then
call Func_CD(attack,"Kolt",3/CD)
else
call Func_CD(attack,"Kolt",0.1)
endif
endif
if GetItemTypeId(UnitItemInSlot(udg_Trophy_build[ID],0))=='bspd' and LoadBoolean(udg_hash,ha,StringHash("Balmung"))==false then
set damage=(0.3*Attacks)*bonus*Psych_crit(hero,1.,1.)
set bj_lastCreatedEffect=AddSpecialEffect("Abilities\\Spells\\Human\\HolyBolt\\HolyBoltSpecialArt.mdl",xt,yt)
call DestroyEffect(bj_lastCreatedEffect)
call UnitDamageTarget(attack,target,damage,false,false,ATTACK_TYPE_CHAOS,DAMAGE_TYPE_UNIVERSAL,WEAPON_TYPE_METAL_LIGHT_CHOP)
set udg_Drop2=ID-1
call GroupEnumUnitsInRange(g,xt,yt,275,Bool_Filter_ID)
call GroupRemoveUnit(g,target)
loop
set u=FirstOfGroup(g)
exitwhen u==null
call UnitDamageTarget(attack,u,damage,false,false,ATTACK_TYPE_CHAOS,DAMAGE_TYPE_UNIVERSAL,WEAPON_TYPE_METAL_LIGHT_CHOP)
call GroupRemoveUnit(g,u)
endloop
call Func_CD(attack,"Balmung",2.25/CD)
endif
set a=0
set i2=0
loop
exitwhen a==6
if GetItemTypeId(UnitItemInSlot(hero,a))=='gopr' then
set i2=1
endif
set a=a+1
endloop
if i2>0 and LoadBoolean(udg_hash,ha,StringHash("Ammeraks"))==false then
set damage=(0.6*Attacks)*bonus*Psych_crit(hero,1.,1.)
set bj_lastCreatedEffect=AddSpecialEffect("Abilities\\Spells\\Human\\HolyBolt\\HolyBoltSpecialArt.mdl",xt,yt)
call DestroyEffect(bj_lastCreatedEffect)
set udg_Drop2=ID-1
call GroupEnumUnitsInRange(g,xt,yt,275,Bool_Filter_ID)
set x=GetUnitState(attack,UNIT_STATE_LIFE)
loop
set u=FirstOfGroup(g)
exitwhen u==null
if x>GetUnitState(u,UNIT_STATE_LIFE)then
call UnitDamageTarget(attack,u,1.5*damage,false,false,ATTACK_TYPE_CHAOS,DAMAGE_TYPE_UNIVERSAL,WEAPON_TYPE_METAL_LIGHT_CHOP)
else
call UnitDamageTarget(attack,u,damage,false,false,ATTACK_TYPE_CHAOS,DAMAGE_TYPE_UNIVERSAL,WEAPON_TYPE_METAL_LIGHT_CHOP)
endif
call GroupRemoveUnit(g,u)
endloop
call Func_CD(attack,"Ammeraks",2./CD)
endif
set a=0
set i2=0
loop
exitwhen a==6
if GetItemTypeId(UnitItemInSlot(hero,a))=='I0BW' then
set i2=1
endif
set a=a+1
endloop
if i2>0 and LoadBoolean(udg_hash,ha,StringHash("GiantHammer"))==false then
set a=175+3*highstat/20
call TempStats(attack,0,0,0,0,a,0,4.)
call Func_CD(attack,"GiantHammer",10.)
endif
set a=0
set i2=0
loop
exitwhen a==6
if GetItemTypeId(UnitItemInSlot(hero,a))=='I07L' then
set i2=1
endif
set a=a+1
endloop
if i2>0 then
set i=GetPlayerId(GetOwningPlayer(attack))+1
set udg_ReflectDmg[i]=(udg_ReflectDmg[i]+6.00)
set bj_lastStartedTimer=CreateTimer()
call SaveInteger(udg_hash,GetHandleId(bj_lastStartedTimer),0,i)
call TimerStart(bj_lastStartedTimer,5.,false,function Trig_AtkSkill_Ghost_Sword)
else
endif
set a=0
set i2=0
loop
exitwhen a==6
if GetItemTypeId(UnitItemInSlot(hero,a))=='I0C2' then
set i2=1
endif
set a=a+1
endloop
if i2==1 and LoadBoolean(udg_hash,ha,StringHash("DeathSpear"))==false then
set damage=(GetHeroAgi(hero,true)*1.4)*bonus
set damage=damage+50
set damage=damage/2
call UnitDamageTarget(attack,target,damage,false,false,ATTACK_TYPE_NORMAL,DAMAGE_TYPE_MAGIC,WEAPON_TYPE_METAL_LIGHT_CHOP)
set bj_lastCreatedEffect=AddSpecialEffectTarget("Abilities\\Spells\\Items\\OrbVenom\\OrbVenomSpecialArt.mdl",target,"origin")
call DestroyEffect(bj_lastCreatedEffect)
set t=CreateTimer()
set ht=GetHandleId(t)
call SaveUnitHandle(udg_hash,ht,0,attack)
call SaveUnitHandle(udg_hash,ht,1,target)
call SaveReal(udg_hash,ht,2,1.5)
call SaveReal(udg_hash,ht,3,damage)
call Func_CD(attack,"DeathSpear",3.5/CD)
call TimerStart(t,0.5,true,function Trig_AtkSkill_DeathPear)
endif
endif
set u=null
call DestroyGroup(g)
set g=null
call DestroyGroup(g2)
set g2=null
set t=null
set str=""
endfunction

```

