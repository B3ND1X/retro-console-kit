// Reuses the console keyboard and native theme-compatible menu components.
class ConsoleNetplay:public GuiComponent {
 std::unique_ptr<MenuComponent> menu;FileData* game;std::future<Result> task;bool waiting=false;std::string operation="status",page="root";std::map<std::string,std::string> values;
 void row(const std::string& name,const std::string& value,std::function<void()> cb=nullptr,bool focus=false){ComponentListRow r;auto t=std::make_shared<TextComponent>(mWindow,name,Font::get(FONT_SIZE_SMALL),0x555555FF);t->setSize(Renderer::getScreenHeight()*.55f,0);r.addElement(t,true);if(!value.empty()){auto v=std::make_shared<TextComponent>(mWindow,value,Font::get(FONT_SIZE_SMALL),0x3377AAFF);v->setSize(Renderer::getScreenHeight()*.27f,0);r.addElement(v,false);}if(cb)r.makeAcceptInputHandler(cb);menu->addRow(r,focus);}
 void note(const std::string& s){ComponentListRow r;auto t=std::make_shared<TextComponent>(mWindow,s,Font::get(FONT_SIZE_SMALL),0x666666FF);t->setSize(Renderer::getScreenHeight()*.85f,0);r.addElement(t,true);menu->addRow(r);}
 void reset(const char* title){if(menu)removeChild(menu.get());menu.reset(new MenuComponent(mWindow,title));addChild(menu.get());}
 void position(){setSize(menu->getSize());setPosition((Renderer::getScreenWidth()-mSize.x())/2,(Renderer::getScreenHeight()-mSize.y())/2);}
 std::vector<std::string> identity(){return {game->getSystem()->getName(),game->getPath()};}
 void query(const std::string& op,const std::vector<std::string>& extra={}){operation=op;std::vector<std::string> args={"netplay",op};if(game&&(op=="status"||op=="rooms"||op=="arm"||op=="room")){auto id=identity();args.insert(args.end(),id.begin(),id.end());}args.insert(args.end(),extra.begin(),extra.end());task=start(args);waiting=true;reset("NETPLAY");note(op=="rooms"?"Checking matching online rooms... B cancels.":"Preparing Netplay...");position();}
 void edit(const std::string& key,const std::string& title){auto upper=key;std::transform(upper.begin(),upper.end(),upper.begin(),::toupper);auto initial=values[upper];mWindow->pushGui(new ConsoleSettingsKeyboard(mWindow,title,initial,false,[this,key](const std::string& value){query("set",{key,value});}));}
 void arm(const std::string& mode){std::string required="\nRequired core/version: "+values["CORE"]+"\nUse matching RetroArch versions where possible (this Pi: 1.10.0).";mWindow->pushGui(new GuiMsgBox(mWindow,(std::string(mode=="host-relay"?"Host this game in the public RetroArch lobby? Both players need identical games and matching core versions. Online play may need more CPU than offline play.":mode=="host-lan"?"Host a direct session? Players on your Wi-Fi can join this console's IP address. Internet joining requires router port forwarding.":"Join this address using the selected game and core? Both players must use matching versions.")+required),"CANCEL",nullptr,"START",[this,mode]{query("arm",mode=="join"?std::vector<std::string>{mode,values["ADDRESS"]}:std::vector<std::string>{mode});}));}
 void populate(const Result& result){
  if(!result.first){page="error";reset("NETPLAY");auto message=result.second;if(message.find("ERROR\t")==0)message.erase(0,6);note("Connection not started. No settings were changed.");row("VIEW DETAILS","",[this,message]{mWindow->pushGui(new GuiMsgBox(mWindow,message));},true);row("TRY AGAIN","",[this]{query("status");});finish();mWindow->pushGui(new GuiMsgBox(mWindow,message));return;}
  if(operation=="arm"||operation=="room"){
   auto g=game;auto w=mWindow;while(w->peekGui()!=ViewController::get())delete w->peekGui();ViewController::get()->launch(g);return;
  }
  if(operation=="set"||operation=="cancel"){query("status");return;}
  if(operation=="rooms"){
   page="rooms";reset("MATCHING ONLINE ROOMS");bool first=true;
   for(auto&r:rows(result.second))if(r.size()>2&&r[0]=="ROOM"){auto id=r[1];row(r[2],"JOIN",[this,id]{query("room",{id});},first);first=false;}else if(r.size()>5&&r[0]=="MISMATCH"){auto message="CORE MISMATCH - cannot join this room.\nHost requires: "+r[2]+" "+r[3]+"\nThis console uses: "+r[4]+" "+r[5]+"\nBoth players must use the host core and exact version/build. Change Emulator if the required core is installed, or use matching compatible binaries. Your core settings were not changed.";row(r[1],"CORE MISMATCH",[this,message]{mWindow->pushGui(new GuiMsgBox(mWindow,message));},first);first=false;}else if(r.size()>1&&r[0]=="NOTE")note(r[1]);
   row("REFRESH ROOMS","",[this]{query("rooms");},first);finish();return;
  }
  values.clear();for(auto&r:rows(result.second))if(r.size()>1&&r[0]!="NOTE")values[r[0]]=r[1];page="root";reset("NETPLAY");
  if(game){note(game->getName());
   if(values["READY"]=="true"){
    row("HOST ONLINE","PUBLIC RELAY",[this]{arm("host-relay");},true);
    row("JOIN ONLINE ROOM","MATCH THIS GAME",[this]{query("rooms");});
    row("HOST ON LOCAL NETWORK","DIRECT",[this]{arm("host-lan");});
    row("JOIN BY ADDRESS","",[this]{if(values["ADDRESS"].empty())edit("address","HOST IP ADDRESS OR HOSTNAME");else arm("join");});
   }else{page="unsupported";for(auto&r:rows(result.second))if(r.size()>1&&r[0]=="NOTE")note(r[1]);}
   if(values.count("CORE"))note("CORE: "+values["CORE"]);
  }else note("Highlight a game, hold X, then choose NETPLAY.\nNormal game launches stay offline.");
  row("PLAYER NAME",values["NICKNAME"],[this]{edit("nickname","NETPLAY PLAYER NAME");},!game||page=="unsupported");
  row("HOST ADDRESS",values["ADDRESS"].empty()?"NOT SET":values["ADDRESS"],[this]{edit("address","HOST IP ADDRESS OR HOSTNAME");});
  row("PORT",values["PORT"],[this]{edit("port","NETPLAY PORT (DEFAULT 55435)");});
  row("RELAY REGION",values["RELAY"],[this]{std::vector<std::string> regions={"nyc","madrid","saopaulo","singapore"};auto i=std::find(regions.begin(),regions.end(),values["RELAY"]);query("set",{"relay",regions[(i==regions.end()?0:i-regions.begin()+1)%regions.size()]});});
  row("HOW TO PLAY","",[this]{mWindow->pushGui(new GuiMsgBox(mWindow,"Host: hold X on a multiplayer game > Netplay > Host Online.\nFriend: highlight the identical game > Netplay > Join Online Room.\nUse identical core versions; RetroArch checks compatibility. Password rooms are omitted.\nFor local play use Host On Local Network and Join By Address.\nSave-state auto resume is disabled only during Netplay.\nExit with your usual exit controls or RESET. No link-cable emulation."));});
  note("THIS CONSOLE: "+values["IP"]);finish();
 }
 void finish(){menu->addButton("BACK","return",[this]{back();});position();LOG(LogInfo)<<"Console Netplay ready: "<<page;}
 void back(){if(page=="rooms"||page=="error"){query("status");return;}delete this;}
public:
 ConsoleNetplay(Window*w,FileData*g=nullptr):GuiComponent(w),game(g?g->getSourceFileData():nullptr){query("status");}
 bool ready()const{return !waiting;}std::string current()const{return page;}
 void update(int dt)override{GuiComponent::update(dt);if(waiting&&task.wait_for(std::chrono::milliseconds(0))==std::future_status::ready){auto r=task.get();waiting=false;populate(r);}}
 bool input(InputConfig*c,Input i)override{if(i.value&&c->isMappedTo("b",i)){if(waiting){if(operation=="arm"||operation=="room")return true;delete this;return true;}back();return true;}if(waiting)return true;return GuiComponent::input(c,i);}
 HelpStyle getHelpStyle()override{return style();}
 std::vector<HelpPrompt>getHelpPrompts()override{return {{"up/down","option"},{"a","select"},{"b","back"}};}
};
