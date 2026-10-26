// Native casting settings; network work stays behind the bounded asynchronous helper.
class ConsoleCasting:public GuiComponent {
 std::unique_ptr<MenuComponent> menu;std::future<Result> task;bool waiting=false;bool advanced=false;std::string op="status";std::map<std::string,std::string> state;int refresh=0;
 void row(const std::string& label,const std::string& value,std::function<void()> callback=nullptr){ComponentListRow r;auto t=std::make_shared<TextComponent>(mWindow,label,Font::get(FONT_SIZE_SMALL),0x555555FF);t->setSize(Renderer::getScreenHeight()*.60f,0);r.addElement(t,true);if(!value.empty())r.addElement(std::make_shared<TextComponent>(mWindow,value,Font::get(FONT_SIZE_SMALL),0x3377AAFF),false);if(callback)r.makeAcceptInputHandler(callback);menu->addRow(r);}
 void request(const std::string& action,const std::string& data="{}"){if(waiting)return;op=action;task=start({"casting",action},data);waiting=true;}
 void note(const std::string& s){mWindow->pushGui(new GuiMsgBox(mWindow,s,"OK",nullptr));}
 bool on(const std::string& key){return state[key]=="True";}
 void toggle(const std::string& key){std::string setting=key;std::transform(setting.begin(),setting.end(),setting.begin(),::tolower);request("settings","{"+json(setting)+":"+(on(key)?"false":"true")+"}");}
 void show(){
  if(menu)removeChild(menu.get());menu.reset(new MenuComponent(mWindow,"CASTING & AIRPLAY"));addChild(menu.get());
  if(!advanced){
   row("YOUTUBE CASTING",on("YOUTUBE")?"ON":"OFF",[this]{toggle("YOUTUBE");});
   row("AIRPLAY",on("AIRPLAY")?"ON":"OFF",[this]{toggle("AIRPLAY");});
   row("LOCAL NETWORK CASTING",on("LOCAL")?"ON":"OFF",[this]{toggle("LOCAL");});
   row("STATUS",state["SOURCE"]=="None"?"READY":state["SOURCE"]+" / "+state["STATE"]);
   row("DISCONNECT","",[this]{request("control","{\"action\":\"disconnect\"}");});
   row("MORE OPTIONS","",[this]{mWindow->pushGui(new ConsoleCasting(mWindow,true));});
   menu->addButton("BACK","return",[this]{delete this;});setSize(menu->getSize());setPosition((Renderer::getScreenWidth()-mSize.x())/2,(Renderer::getScreenHeight()-mSize.y())/2);return;
  }
  row("DEVICE NAME",state["NAME"],[this]{mWindow->pushGui(new ConsoleSettingsKeyboard(mWindow,"CAST DEVICE NAME",state["NAME"],false,[this](const std::string& s){request("settings","{\"name\":"+json(s)+"}");}));});
  row("YOUTUBE CASTING",on("YOUTUBE")?"ON":"OFF",[this]{toggle("YOUTUBE");});
  row("LOCAL NETWORK CASTING",on("LOCAL")?"ON":"OFF",[this]{toggle("LOCAL");});
  row("AIRPLAY",on("AIRPLAY")?"ON":"OFF",[this]{toggle("AIRPLAY");});
  row("MAX VIDEO QUALITY",state["MAX_HEIGHT"]+"p",[this]{request("settings",std::string("{\"max_height\":")+(state["MAX_HEIGHT"]=="720"?"1080":"720")+"}");});
  row("YOUTUBE CONNECTION",state["YOUTUBE_STATUS"]);
  row("DISCOVERY",state["DISCOVERY"]);row("PAIRED YOUTUBE PHONES",state["PAIRED_PHONES"]);
  row("LINK YOUTUBE WITH TV CODE",state["TV_CODE"].empty()?"GET CODE":state["TV_CODE"],[this]{request("tv-code");});
  row("PAIR LOCAL PHONE",state["PIN"].empty()?"SHOW PIN":state["PIN"],[this]{request("pin");});
  row("AUTHORIZED LOCAL CLIENTS",state["LAN_CLIENTS"]+"  / FORGET",[this]{request("forget-clients");});
  row("PHONE CONTROL PAGE","VIEW",[this]{note("On the same Wi-Fi, open http://CONSOLE-IP:8010 on your phone.\nEnable Local Network Casting, then select Pair Local Phone and enter its PIN.\n\nThe private LAN page supports direct MP4/HLS links, queue, pause, seek, volume and stop. Find the console IP in Developer Tools > Device Info.");});
  row("AIRPLAY SUPPORT","AUDIO + MIRRORING",[this]{note("Turn AirPlay ON, then select SNES Console on your iPhone.\nThe console stays visible until a session starts.\n\nAudio output and Control Center screen mirroring are supported. Direct video handoff from apps is not supported by this legacy receiver.\n\nGames are protected. Use only a trusted home network; mirroring has no PIN.");});
  row("AIRPLAY STATUS",state["AIRPLAY_STATUS"]);
  row("AIRPLAY AUDIO PASSWORD",state["AIRPLAY_PASSWORD"]=="True"?"SET":"NOT SET",[this]{mWindow->pushGui(new ConsoleSettingsKeyboard(mWindow,"AIRPLAY AUDIO PASSWORD",std::string(),true,[this](const std::string& s){request("settings","{\"airplay_password\":"+json(s)+"}");}));});
  row("CURRENT SOURCE",state["SOURCE"]);row("SESSION",state["STATE"]);
  row("PAUSE / RESUME","",[this]{request("control","{\"action\":"+json(state["STATE"]=="paused"?"resume":"pause")+"}");});
  row("DISCONNECT SESSION","",[this]{request("control","{\"action\":\"disconnect\"}");});
  row("DURING GAMES","BLOCK CASTS",[this]{note("Games, LookMovie and software updates are protected.\nReturn to the game library before starting a cast.\nCasting never automatically exits a game.");});
  row("MUSIC DURING CASTING","PAUSED",[this]{note("Casting owns the audio output while active.\nLocal menu music resumes according to its existing preferences after casting ends.\nExisting Spotify/gameplay preferences are preserved.");});
  row("DIAGNOSTICS / REFRESH",state["ERROR"].empty()?"OK":"VIEW",[this]{note("YouTube: "+state["YOUTUBE_STATUS"]+"\nDiscovery: "+state["DISCOVERY"]+"\nPaired YouTube phones: "+state["PAIRED_PHONES"]+"\nAuthorized LAN clients: "+state["LAN_CLIENTS"]+"\n"+state["ERROR"]);request("status");});
  row("RESTART RECEIVERS","",[this]{request("restart");});
  menu->addButton("BACK","return",[this]{delete this;});setSize(menu->getSize());setPosition((Renderer::getScreenWidth()-mSize.x())/2,(Renderer::getScreenHeight()-mSize.y())/2);
 }
public:
 ConsoleCasting(Window*w,bool expanded=false):GuiComponent(w),advanced(expanded){show();request("status");}
 bool ready()const{return !waiting;}
 void update(int dt)override{
  GuiComponent::update(dt);if(!waiting){refresh+=dt;if(refresh>2000&&state["TV_CODE"]=="Fetching code..."){refresh=0;request("status");}return;}if(task.wait_for(std::chrono::milliseconds(0))!=std::future_status::ready)return;auto r=task.get();waiting=false;
  if(!r.first){note(r.second);return;}
  if(op!="status"){request("status");return;}
  for(auto v:rows(r.second))if(v.size()>1)state[v[0]]=v[1];show();
 }
 bool input(InputConfig*c,Input i)override{if(i.value&&c->isMappedTo("b",i)){delete this;return true;}if(waiting)return true;if(i.value&&c->isMappedTo("x",i)){request("status");return true;}return menu->input(c,i);}
 HelpStyle getHelpStyle()override{return style();}
 std::vector<HelpPrompt> getHelpPrompts()override{return {{"a","select"},{"b","back"},{"x","refresh"}};}
};
static std::string castField(const std::string& text,const std::string& key){auto n=text.find("\""+key+"\"");if(n==std::string::npos)return "";n=text.find(':',n);if(n==std::string::npos)return "";n=text.find('"',n);if(n==std::string::npos)return "";auto end=text.find('"',n+1);return end==std::string::npos?"":text.substr(n+1,end-n-1);}
static void consoleCastingTick(Window*w,int dt){
 static int elapsed=0;static bool running=false;static std::string seen;elapsed+=dt;if(running||elapsed<500)return;elapsed=0;
 std::ifstream f("/dev/shm/snes-casting-"+std::to_string(getuid())+".json");if(!f)return;std::string text((std::istreambuf_iterator<char>(f)),std::istreambuf_iterator<char>());if(text.size()>8192||castField(text,"phase")!="pending")return;
 auto id=castField(text,"id");if(id.empty()||id==seen)return;seen=id;
 int fd=open("/run/snes-updater/game.lock",O_RDONLY|O_CLOEXEC);if(fd<0)return;if(flock(fd,LOCK_EX|LOCK_NB)!=0){close(fd);return;}
 auto claimed=command({"casting","claim"},"{\"id\":"+json(id)+"}");if(!claimed.first){close(fd);return;}
 running=true;AudioManager::getInstance()->deinit();VolumeControl::getInstance()->deinit();w->deinit();runSystemCommand("/usr/bin/python3 /usr/local/lib/snes-console/casting/player.py");w->init();VolumeControl::getInstance()->init();w->normalizeNextUpdate();close(fd);running=false;
 auto r=command({"casting","status"});if(r.first)for(auto v:rows(r.second))if(v.size()>1&&v[0]=="ERROR"&&!v[1].empty())w->pushGui(new GuiMsgBox(w,v[1],"OK",nullptr));
}
