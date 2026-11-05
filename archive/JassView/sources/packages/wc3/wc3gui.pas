unit wc3gui;

{$mode objfpc}{$H+}
{$asmmode intel}

interface

uses
	wc3main, wc3collections, wc3refcnt, wc3observer;

type
    TUnknownHashtable = specialize TSHashTable<Pointer, specialize TSHashObject<Pointer>, THashlessKeyManager>;
	TUnknownArray = specialize TSArray<Pointer>;
	TUnknownGrowableArray = specialize TSGrowableArray<Pointer>;
	TUnknownLinkedList = specialize TSLinkedList<Pointer, TMissingInitialOffset>;

    PFrame = Pointer;

	PLayerNode = ^TLayerNode;
	TLayerNode = object
		vtable: Pointer;
		Node: specialize TSLinkedNode<PLayerNode>;
		Value: PFrame;
	end;

	TLayer_VMT = object (TObserver_VMT)
		method18: procedure; stdcall;
		method1C: procedure; stdcall;
		method20: procedure; stdcall;
		method24: procedure; stdcall;
		method28: procedure; stdcall;
		method2C: procedure; stdcall;
		method30: procedure; stdcall;
		method34: procedure; stdcall;
		method38: procedure; stdcall;
		method3C: procedure; stdcall;
		method40: procedure; stdcall;
		method44: procedure; stdcall;
		method48: procedure; stdcall;
		method4C: procedure; stdcall;
		method50: procedure; stdcall;
		method54: procedure; stdcall;
		method58: procedure; stdcall;
		method5C: procedure; stdcall;
		method60: procedure; stdcall;
		method64: procedure; stdcall;
		method68: procedure; stdcall;
		method6C: procedure; stdcall;
		method70: procedure; stdcall;
		method74: procedure; stdcall;
		method78: procedure; stdcall;
		method7C: procedure; stdcall;
		method80: procedure; stdcall;
		method84: procedure; stdcall;
		method88: procedure; stdcall;
		method8C: procedure; stdcall;
		method90: procedure; stdcall;
		method94: procedure; stdcall;
		method98: procedure; stdcall;
		method9C: procedure; stdcall;
		methodA0: procedure; stdcall;
		OnAlphaUpdated_: procedure; stdcall;
		methodA8: procedure; stdcall;
		methodAC: procedure; stdcall;
		methodB0: procedure; stdcall;
		methodB4: procedure; stdcall;
		methodB8: procedure; stdcall;
		methodBC: procedure; stdcall;
		methodC0: procedure; stdcall;
		methodC4: procedure; stdcall;
		methodC8: procedure; stdcall;
		methodCC: procedure; stdcall;
		methodD0: procedure; stdcall;
		methodD4: procedure; stdcall;
		methodD8: procedure; stdcall;
	end;
	PLayer_VMT = ^TLayer_VMT;

	PLayer = ^TLayer;
	TLayer = object (TObserver)
		flags0C_: Dword;
		flags10_: Dword;
		childs: specialize TSLinkedList<TLayerNode, TMissingInitialOffset>;
		parent: PLayer;
		constructor_a3: Dword;
		field28: Dword;
		field2C: Dword;
		field30: Dword;
		float34: Single;
		field38: Dword;
		field3C: Dword;
		field40: Dword;
		field44_this: PLayer;
		field48: Dword;
		field4C: Dword;
		field50: Dword;
		field54: Dword;
		field58: Dword;
		field5C: Dword;
		field60: Dword;
		field64: Dword;
		field68_this: PLayer;
		float6C: Single;
		float70: Single;
		list74: TUnknownLinkedList;
		ShortcutsTable_: TUnknownHashtable;
		constructor_a4: Dword;
		color_: Dword;
		flags: Dword;
	end;

	TLayoutFrame_VMT = object
		method00: procedure; stdcall;
		method04: procedure; stdcall;
		method08: procedure; stdcall;
		method0C: procedure; stdcall;
		method10: procedure; stdcall;
		method14: procedure; stdcall;
		method18: procedure; stdcall;
		method1C: procedure; stdcall;
		method20: procedure; stdcall;
	end;
	PLayoutFrame_VMT = ^TLayoutFrame_VMT;

	PLayoutFrame = ^TLayoutFrame;

	TFramePoint_VMT = object
		Delete: procedure (FreeMemory: Boolean); stdcall;
		method04: procedure; stdcall;
		method08: procedure; stdcall;
		GetLayoutFrame: function: PLayoutFrame;
	end;

	TFramePoint = object
		vtable: Pointer;
	end;
	PFramePoint = ^TFramePoint;

	PFrameNode = ^TFrameNode;
	TFrameNode = object
		vtable: Pointer;
		Node: specialize TSLinkedNode<PFrameNode>;
		Value: Dword;
		Flags_: Dword;
	end;

	TLayoutFrame = object
		vtable: Pointer;
		Count: Dword;
		FramePoints: array [0..8] of PFramePoint;
		field2C: Dword;
		Node: specialize TSLinkedNode<Pointer>;
		Childs_: specialize TSLinkedList<TFrameNode, TMissingInitialOffset>;
		Rect_: array [0..3] of Single;
		Enabled_: Dword;
		Width_: Single;
		Height_: Single;
		field60: Single;
		field64: Single;
	end;

	TFrame_VMT = object (TLayer_VMT)
		methodDC: procedure; stdcall;
		methodE0: procedure; stdcall;
	end;

	TFrame = object (TLayer)
		LayoutFrame: TLayoutFrame;
		field11C: Dword;
		field120: Dword;
		field124: Dword;
		field128: Dword;
		field12C: Single;
		field130: Single;
		field134: Single;
		field138: Single;
		field13C: Single;
		field140: Dword;
		list144: TUnknownLinkedList;
		list150: TUnknownLinkedList;
		field15C: Dword;
		field160: Dword;
		field164: Dword;
	end;

	TScreenFrame = object (TFrame)
		field168: Dword;
		field16C: Dword;
		objects170: array [0..3] of PRefCnt;
	end;
	PScreenFrame = ^TScreenFrame;

	TSimpleFrame_VMT = object (TLayoutFrame_VMT)
		method24: procedure; stdcall;
		method28: procedure; stdcall;
		OnShow_: procedure; stdcall;
		OnHide_: procedure; stdcall;
		method34: procedure; stdcall;
		method38: procedure; stdcall;
		method3C: procedure; stdcall;
		method40: procedure; stdcall;
		method44: procedure; stdcall;
		method48: procedure; stdcall;
		method4C: procedure; stdcall;
		method50: procedure; stdcall;
		method54: procedure; stdcall;
		method58: procedure; stdcall;
		method5C: procedure; stdcall;
		method60: procedure; stdcall;
		Hide: procedure; stdcall;
		Show: procedure; stdcall;
	end;
	PSimpleFrame_VMT = ^TSimpleFrame_VMT;

	TSimpleFrame = object (TLayoutFrame)
		ParentTop_: Dword; // PSimpleTop
		field6C: Dword;
		field70: Dword;
		field74: Dword;
		field78: Dword;
		field7C: Dword;
		field80: Dword;
		UpdateOnZOrderChange_: Dword;
		field88: Dword;
		field8C: Dword;
		CanBeShown_: Dword;
		Visible_: LongBool;
		field98: Single;
		field9C: Single;
		fieldA0: Single;
		fieldA4: Single;
		fieldA8: Single;
		fieldAC: Single;
		fieldB0: Single;
		fieldB4: Single;
		fieldB8: Dword;
		fieldBC: Dword;
		fieldC0: Dword;
		fieldC4: Dword;
		fieldC8: Dword;
		fieldCC: Dword;
		listD0: TUnknownLinkedList;
		listsDC: array [0..4] of TUnknownLinkedList;
		childs2_: TUnknownLinkedList;
	end;
	PSimpleFrame = ^TSimpleFrame;

	TMessageData = record
		Message: PChar;
		Color: Dword;
		Duration: Single;
		Permanent: LongBool;
	end;
	PMessageData = ^TMessageData;

	TSimpleMessageFrame_VMT = object (TSimpleFrame_VMT)
		Print: procedure (Message: PChar; pColor: PDword; Duration: Single; Permanent: LongBool); stdcall;
	end;
	PSimpleMessageFrame_VMT = ^TSimpleMessageFrame_VMT;

	{ TSimpleMessageFrame }

	TSimpleMessageFrame = object (TSimpleFrame)
		lines_count_: Dword;
		field128: Dword;
		font_path: PChar;
		font_height: Single;
		field134_forfont: Dword;
		max_line_length_: Dword;
		field13C: Dword;
		default_text_color_: Dword;
		floats144: array [0..1] of Single;
		field14C: Single;
		field150: Single;
		field154: Single;
		field158: Single;
		field15C: Single;
		field160: Single;
		field164: Single;
		field168: Single;
		field16C: Single;
		field170: Dword;
		Messages: specialize TSGrowableArray<TMessageData>;
		field184: Dword;
		field188: Dword;
		field18C: Dword;
		field190: Dword;
	public
		procedure Print(AMessage: String; Duration: Single = 10.0; Color: Dword = $FFFFFFFF; Permanent: Boolean = False);
	end;
	PSimpleMessageFrame = ^TSimpleMessageFrame;

	PGameUI = ^TGameUI;

	{ TGameUI }

	TGameUI = object (TScreenFrame)
		interface_state_: Dword;
		FontCache: TUnknownHashtable;
		UserControlEnabled: LongBool;
		UserUIEnabled: LongBool;
		InputMode: Dword;
		InputModes: TUnknownGrowableArray;
		ToolTip: Dword;
		UberToolTip: Dword;
		ShowDescriptions: LongBool;
		field1D4: Dword;
		field1D8: Dword;
		ShowMinimapSignals: LongBool;
		field1E0: Dword;
		field1E4: Dword;
		field1E8: Dword;
		field1EC: Dword;
		field1F0: Dword;
		field1F4: Dword;
		field1F8: Dword;
		field1FC: Dword;
		field200: Dword;
		field204: Dword;
		field208: Dword;
		field20C: Dword;
		TargetMode: Dword;
		SelectMode: Dword;
		field218: Dword;
		field21C: Dword;
		BuildMode: Dword;
		SignalMode: Dword;
		EscMenu: Dword;
		field22C: Dword;
		SuspendIndicator: Dword;
		UnresponsiveIndicator: Dword;
		AllianceMode: Dword;
		ChatMode: Dword;
		QuestMode: Dword;
		ScriptDialogMode: Dword;
		field248: Dword;
		field24C: Dword;
		field250: Dword;
		Camera: Pointer; // PCameraWar3
		field258: Dword;
		field25C: Dword;
		field260: Dword;
		field264: Dword;
		field268: Dword;
		NeedUpdateUnitUI: LongBool;
		field270: Dword;
		NeedUpdateSelection: LongBool;
		NeedUpdateInfoBar: LongBool;
		NeedUpdateCommandBar: LongBool;
		NeedUpdateHeroBar: LongBool;
		flags284_: Dword;
		field288: Dword;
		ForceCinematicSubtitles: LongBool;
		DragSelectEnabled: LongBool;
		DragSelectUIEnabled: LongBool;
		PreSelectEnabled: LongBool;
		PreSelectUIEnabled: LongBool;
		SelectionEnabled: LongBool;
		SelectionUIEnabled: LongBool;
		field2A8: Dword;
		field2AC: Dword;
		field2B0: Dword;
		field2B4: Dword;
		field2B8: Dword;
		field2BC: Dword;
		field2C0: Dword;
		field2C4: Dword;
		field2C8: Dword;
		field2CC: Dword;
		field2D0: Dword;
		field2D4: Dword;
		field2D8: Dword;
		field2DC: Dword;
		field2E0: Dword;
		field2E4: Dword;
		field2E8: Dword;
		field2EC: Dword;
		field2F0: Dword;
		field2F4: Dword;
		field2F8: Dword;
		field2FC: Dword;
		field300: Dword;
		field304: Dword;
		field308: Dword;
		field30C: Dword;
		field310: Dword;
		field314: Dword;
		field318: Dword;
		field31C: Dword;
		field320: Dword;
		field324: Dword;
		field328: Dword;
		field32C: Dword;
		field330: Dword;
		field334: Dword;
		field338: Dword;
		field33C: Dword;
		field340: Dword;
		field344: Dword;
		field348: Dword;
		field34C: Dword;
		field350: Dword;
		field354: Dword;
		field358: Dword;
		field35C: Dword;
		field360: Dword;
		field364: Dword;
		field368: Dword;
		field36C: Dword;
		field370: Dword;
		field374: Dword;
		field378: Dword;
		field37C: Dword;
		field380: Dword;
		field384: Dword;
		field388: Dword;
		field38C: Dword;
		field390: Dword;
		field394: Dword;
		field398: Dword;
		field39C: Dword;
		field3A0: Dword;
		field3A4: Dword;
		field3A8: Dword;
		field3AC: Dword;
		field3B0: Dword;
		field3B4: Dword;
		field3B8: Dword;
		field3BC: Dword;
		field3C0: Dword;
		field3C4: Dword;
		field3C8: Dword;
		field3CC: Dword;
		field3D0: Dword;
		field3D4: Dword;
		field3D8: Dword;
		field3DC: Dword;
		field3E0: Dword;
		field3E4: Dword;
		field3E8: Dword;
		WorldFrameChatMessage: PSimpleMessageFrame;
		field3F0: Dword;
		field3F4: Dword;
		field3F8: Dword;
		field3FC: Dword;
		field400: Dword;
		field404: Dword;
		field408: Dword;
		field40C: Dword;
		field410: Dword;
		field414: Dword;
		field418: Dword;
		field41C: Dword;
		field420: Dword;
		field424: Dword;
		field428: Dword;
		field42C: Dword;
		field430: Dword;
		field434: Dword;
		field438: Dword;
		field43C: Dword;
		field440: Dword;
		field444: Dword;
		field448: Dword;
		field44C: Dword;
		field450: Dword;
	private
		class function GetInstance: PGameUI; static;
	public
		class property Instance: PGameUI read GetInstance;
	end;

var
	ppGameUI: ^PGameUI;

implementation

procedure OnInit;
begin
	Pointer(ppGameUI):= Pointer(GameDll + $AB4F80);
end;

{ TGameUI }

class function TGameUI.GetInstance: PGameUI;
begin
	Result:= ppGameUI^;
end;

{ TSimpleMessageFrame }

procedure TSimpleMessageFrame.Print(AMessage: String; Duration: Single;
	Color: Dword; Permanent: Boolean);
begin
	asm mov ecx, Self end;
	PSimpleMessageFrame_VMT(vtable)^.Print(PChar(AMessage), @Color, Duration, Permanent);
end;

initialization
	wc3main.SubscribeOnInit(@OnInit);

end.

