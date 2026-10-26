// Native on-demand movie search and playback. No browser or permanent media process.
class ConsoleMedia:public GuiComponent {
 std::unique_ptr<MenuComponent> menu;std::future<Result> task;bool waiting=false;std::string page="root",operation,title,session;std::vector<std::vector<std::string>> matches;std::vector<std::string> qualities;
 void row(const std::string& label,const std::string& value="",std::function<void()> callback=nullptr){ComponentListRow r;auto a=std::make_shared<TextComponent>(mWindow,label,Font::get(FONT_SIZE_SMALL),0x555555FF);a->setSize(Renderer::getScreenHeight()*.68f,0);r.addElement(a,true);if(!value.empty()){auto b=std::make_shared<TextComponent>(mWindow,value,Font::get(FONT_SIZE_SMALL),0x3377AAFF);r.addElement(b,false);}if(callback)r.makeAcceptInputHandler(callback);menu->addRow(r);}
 void reset(const std::string& label){if(menu)removeChild(menu.get());menu.reset(new MenuComponent(mWindow,label.c_str()));addChild(menu.get());}
 void finish(){menu->addButton("BACK","return",[this]{back();});setSize(menu->getSize());setPosition((Renderer::getScreenWidth()-mSize.x())/2,(Renderer::getScreenHeight()-mSize.y())/2);LOG(LogInfo)<<"Console video player ready: "<<page;}
 void message(const std::string& s){mWindow->pushGui(new GuiMsgBox(mWindow,s,"OK",nullptr));}
 void keyboard(const std::string& name,const std::string& op,const std::string& field){mWindow->pushGui(new ConsoleSettingsKeyboard(mWindow,name,"",false,[this,op,field](const std::string& value){request(op,"{"+json(field)+":"+json(value)+"}");}));}
 void root(){page="root";reset("VIDEO PLAYER");row("SEARCH MOVIES","",[this]{keyboard("SEARCH LOOKMOVIE MOVIES","search","query");});row("OPEN MOVIE LINK","",[this]{keyboard("LOOKMOVIE MOVIE PAGE URL","resolve","url");});if(!qualities.empty())row("RETURN TO MOVIE","",[this]{quality();});row("PLAYBACK CONTROLS","VIEW",[this]{message("A: play / pause\nB: stop and return\nLeft / Right: seek\nUp / Down: volume\nY: stop and choose quality; resume where supported\n\nMovies only in this first version. The website decides which qualities are available. No browser, login or challenge bypass.");});finish();}
 void results(){page="results";reset("LOOKMOVIE SEARCH");if(matches.empty())row("NO MOVIES FOUND");for(auto r:matches){if(r.size()<5)continue;row(r[2],r[3],[this,r]{request("resolve","{\"url\":"+json(r[4])+"}");});}finish();}
 void quality(){page="quality";reset(title.empty()?"CHOOSE QUALITY":title);for(auto q:qualities)row("PLAY",q,[this,q]{request("prepare","{\"quality\":"+json(q)+",\"session\":"+json(session)+"}");});row("A PAUSE / B BACK / Y QUALITY");finish();}
 void request(const std::string& op,const std::string& data="{}"){if(waiting)return;operation=op;task=start({"media",op},data);waiting=true;reset(op=="search"?"SEARCHING MOVIES":"VIDEO PLAYER");row(op=="resolve"?"GETTING AVAILABLE STREAMS...":"PLEASE WAIT...");finish();}
 void play(){
  int fd=open("/run/snes-updater/game.lock",O_RDONLY|O_CLOEXEC);if(fd>=0&&flock(fd,LOCK_EX|LOCK_NB)!=0){close(fd);message("Wait for the software update to finish before watching a video.");quality();return;}
  // Follow the same renderer/audio handoff as normal game launch, without changing game metadata.
  AudioManager::getInstance()->deinit();VolumeControl::getInstance()->deinit();mWindow->deinit();
  runSystemCommand("/usr/bin/python3 /usr/local/lib/snes-console/media.py play");
  mWindow->init();VolumeControl::getInstance()->init();mWindow->normalizeNextUpdate();if(fd>=0)close(fd);request("status");
 }
 void back(){if(waiting){delete this;return;}if(page=="root"){delete this;return;}if(page=="quality"&&!matches.empty())results();else root();}
public:
 ConsoleMedia(Window*w):GuiComponent(w){root();}
 bool ready()const{return !waiting;}
 std::string current()const{return page;}
 void update(int dt)override{GuiComponent::update(dt);if(!waiting||task.wait_for(std::chrono::milliseconds(0))!=std::future_status::ready)return;auto r=task.get();waiting=false;
  if(!r.first){auto error=r.second;root();message(error);return;}
  auto list=rows(r.second);
  if(operation=="search"){matches.clear();for(auto v:list)if(v.size()>=4&&v[0]=="RESULT")matches.push_back(v);results();}
  else if(operation=="resolve"){qualities.clear();for(auto v:list)if(v.size()>=2){if(v[0]=="TITLE")title=v[1];if(v[0]=="SESSION")session=v[1];if(v[0]=="QUALITY")qualities.push_back(v[1]);}quality();}
  else if(operation=="prepare")play();
  else if(operation=="status"){quality();for(auto v:list)if(v.size()>=2&&v[0]=="ERROR"&&!v[1].empty())message(v[1]);}
 }
 bool input(InputConfig*c,Input i)override{if(i.value&&c->isMappedTo("b",i)){back();return true;}if(waiting)return true;return menu->input(c,i);}
 HelpStyle getHelpStyle()override{return style();}
 std::vector<HelpPrompt> getHelpPrompts()override{return {{"a","select"},{"b","back"}};}
};
