// Native controller manager. Uses RetroPie's established input-configuration wizard.
class ConsoleControllerTrial;
void controllerReload(){
 pugi::xml_document doc;if(!doc.load_file(InputManager::getConfigPath().c_str()))return;auto root=doc.child("inputList");
 for(int n=0;n<SDL_NumJoysticks();n++){auto c=InputManager::getInstance()->getInputConfigByDevice(SDL_JoystickGetDeviceInstanceID(n));if(!c)continue;auto entry=root.find_child_by_attribute("inputConfig","deviceGUID",c->getDeviceGUIDString().c_str());if(!entry)entry=root.find_child_by_attribute("inputConfig","deviceName",c->getDeviceName().c_str());if(entry)c->loadFromXML(entry);else c->clear();}
}
Result controllerCall(const std::string& action){return command({"controllers",action});}
void controllerRestore(){auto r=controllerCall("restore");controllerReload();if(!r.first)LOG(LogError)<<r.second;}
class ConsoleControllerRecovery:public GuiComponent{
 MenuComponent menu;std::shared_ptr<TextComponent> text;Input held;int elapsed=0;bool down=false;
public:
 ConsoleControllerRecovery(Window*w):GuiComponent(w),menu(w,"CONTROLLER RECOVERY"){
  setSize(Renderer::getScreenWidth(),Renderer::getScreenHeight());text=std::make_shared<TextComponent>(w,"Release all buttons.\nThen hold ANY button for 3 seconds to restore the previous controller setup.\nWait 20 seconds to cancel.",Font::get(FONT_SIZE_MEDIUM),0x777777FF);ComponentListRow row;row.addElement(text,true);menu.addRow(row,false);menu.setPosition((mSize.x()-menu.getSize().x())/2,(mSize.y()-menu.getSize().y())/2);addChild(&menu);
 }
 bool input(InputConfig*,Input i)override{if(i.type==TYPE_BUTTON){if(i.value&&!down){down=true;held=i;elapsed=0;}else if(!i.value&&i.device==held.device&&i.id==held.id){down=false;elapsed=0;}}return true;}
 void update(int dt)override{GuiComponent::update(dt);if(down){elapsed+=dt;if(elapsed>=3000){controllerRestore();delete this;return;}}else{elapsed+=dt;if(elapsed>=20000){delete this;return;}}}
};
class ConsoleControllerTrial:public GuiComponent{
 MenuComponent menu;int remaining=20000;std::shared_ptr<TextComponent> timer;
 void finish(bool keep){if(keep)controllerCall("accept");else controllerRestore();delete this;}
public:
 ConsoleControllerTrial(Window*w):GuiComponent(w),menu(w,"KEEP THIS BUTTON SETUP?"){
  setSize(Renderer::getScreenWidth(),Renderer::getScreenHeight());timer=std::make_shared<TextComponent>(w,"Try the new buttons. Restore automatically in 20 seconds.",Font::get(FONT_SIZE_SMALL),0x777777FF);ComponentListRow row;row.addElement(timer,true);menu.addRow(row,false);menu.addButton("KEEP","keep",[this]{finish(true);});menu.addButton("RESTORE","restore",[this]{finish(false);});menu.setCursorToButtons();menu.setPosition((mSize.x()-menu.getSize().x())/2,(mSize.y()-menu.getSize().y())/2);addChild(&menu);
 }
 void update(int dt)override{GuiComponent::update(dt);remaining-=dt;timer->setText("Try the new buttons. Restore automatically in "+std::to_string((remaining+999)/1000)+" seconds.");if(remaining<=0){finish(false);return;}}
 bool input(InputConfig*c,Input i)override{if(i.value&&c->isMappedTo("b",i)){finish(false);return true;}return menu.input(c,i);}
};
class ConsoleSafeControllerWizard:public GuiInputConfig{
 std::shared_ptr<bool> accepted;int elapsed=0,heldTime=0,device;bool held=false;Input button;
 void cancel(){*accepted=true;controllerRestore();delete this;}
public:
 ConsoleSafeControllerWizard(Window*w,InputConfig*target,std::shared_ptr<bool>flag):GuiInputConfig(w,target,true,[w,flag]{*flag=true;controllerReload();w->pushGui(new ConsoleControllerTrial(w));}),accepted(flag),device(target->getDeviceId()){}
 ~ConsoleSafeControllerWizard(){if(!*accepted)controllerRestore();}
 bool input(InputConfig*c,Input i)override{
  if(i.type==TYPE_BUTTON){if(i.value&&!held){button=i;held=true;heldTime=0;}else if(!i.value&&i.device==button.device&&i.id==button.id){held=false;heldTime=0;}}
  return GuiInputConfig::input(c,i);
 }
 void update(int dt)override{
  elapsed+=dt;if(held)heldTime+=dt;
  if(elapsed>240000||heldTime>=8000||!SDL_JoystickFromInstanceID(device)){cancel();return;}
  GuiInputConfig::update(dt);
 }
};
class ConsoleControllerTest:public GuiComponent{
 MenuComponent menu;std::shared_ptr<TextComponent> display;std::vector<std::string> events;int device,heldTime=0,pollTime=0;bool held=false;Input button;
public:
 ConsoleControllerTest(Window*w,int id):GuiComponent(w),menu(w,"TEST CONTROLLER INPUTS"),device(id){setSize(Renderer::getScreenWidth(),Renderer::getScreenHeight());display=std::make_shared<TextComponent>(w,"Press buttons, move the D-pad or sticks.\nHold any button for 2 seconds to return.",Font::get(FONT_SIZE_SMALL),0x555555FF);ComponentListRow row;row.addElement(display,true);menu.addRow(row,false);menu.setSize(Vector2f(mSize.x()*.76f,mSize.y()*.70f));menu.setPosition((mSize.x()-menu.getSize().x())/2,(mSize.y()-menu.getSize().y())/2);addChild(&menu);}
 bool input(InputConfig*c,Input i)override{
  if(i.device!=device)return true;
  if(i.type==TYPE_BUTTON){if(i.value&&!held){held=true;heldTime=0;button=i;}else if(!i.value&&i.id==button.id){held=false;heldTime=0;}}
  std::string names;for(auto&name:c->getMappedTo(i)){if(!names.empty())names+=", ";names+=name;}
  events.push_back(i.string()+" = "+std::to_string(i.value)+(names.empty()?"":"  ["+names+"]"));if(events.size()>6)events.erase(events.begin());return true;
 }
 void update(int dt)override{
  GuiComponent::update(dt);if(held){heldTime+=dt;if(heldTime>=2000){delete this;return;}}
  auto joy=SDL_JoystickFromInstanceID(device);auto config=joy?InputManager::getInstance()->getInputConfigByDevice(device):nullptr;if(!config||!joy){delete this;return;}
  pollTime+=dt;if(pollTime<100)return;pollTime=0;std::string text=config->getDeviceName()+"\n\n";
  for(auto&e:events)text+=e+"\n";text+="\nRaw axes: ";for(int n=0;n<std::min(SDL_JoystickNumAxes(joy),8);n++)text+=std::to_string(n)+":"+std::to_string(SDL_JoystickGetAxis(joy,n))+"  ";text+="\nHold ANY button for 2 seconds to return.";display->setText(text);
 }
};
class ConsoleControllers:public GuiComponent{
 std::unique_ptr<MenuComponent> menu;std::string page="root",deviceKey;int selectedDevice=-1,selectedPort=1;std::future<Result> task;bool loading=false,hasAction=false;std::vector<std::vector<std::string>> data;
 void row(const std::string&name,const std::string&value,std::function<void()> action){ComponentListRow r;r.addElement(std::make_shared<TextComponent>(mWindow,name,Font::get(FONT_SIZE_SMALL),0x555555FF),true);r.elements.back().component->setSize(Renderer::getScreenHeight()*.60f,0);if(!value.empty())r.addElement(std::make_shared<TextComponent>(mWindow,value,Font::get(FONT_SIZE_SMALL),0x777777FF,ALIGN_RIGHT),false);if(!value.empty())r.elements.back().component->setSize(Renderer::getScreenHeight()*.28f,0);r.makeAcceptInputHandler(action);menu->addRow(r,!hasAction);hasAction=true;}
 void note(const std::string&value){ComponentListRow r;r.addElement(std::make_shared<TextComponent>(mWindow,value,Font::get(FONT_SIZE_SMALL),0x777777FF),true);menu->addRow(r,false);}
 void reset(const std::string&title){hasAction=false;if(menu)removeChild(menu.get());menu.reset(new MenuComponent(mWindow,title.c_str()));addChild(menu.get());}
 void done(){menu->addButton("BACK","back",[this]{back();});menu->setPosition((mSize.x()-menu->getSize().x())/2,(mSize.y()-menu->getSize().y())/2);}
 void refresh(){loading=true;task=start({"controllers","status"});reset("CONTROLLER MANAGER");note("Loading controllers...");done();}
 void action(std::vector<std::string> args){args.insert(args.begin(),"controllers");loading=true;task=start(args);reset("CONTROLLER MANAGER");note("Saving controller settings...");done();}
 void setup(){auto c=SDL_JoystickFromInstanceID(selectedDevice)?InputManager::getInstance()->getInputConfigByDevice(selectedDevice):nullptr;if(!c){refresh();return;}mWindow->pushGui(new GuiMsgBox(mWindow,"Set up "+c->getDeviceName()+"?\nThe current mappings will be protected. Hold any button for 8 seconds to cancel setup. Unconfirmed mappings restore automatically.","CANCEL",nullptr,"SET UP",[this]{auto c=SDL_JoystickFromInstanceID(selectedDevice)?InputManager::getInstance()->getInputConfigByDevice(selectedDevice):nullptr;if(!c)return;auto r=controllerCall("begin");if(!r.first){mWindow->pushGui(new GuiMsgBox(mWindow,r.second));return;}mWindow->pushGui(new ConsoleSafeControllerWizard(mWindow,c,std::make_shared<bool>(false)));}));}
 void show(){
  if(page=="root"){
   reset("CONTROLLER MANAGER");row("CONNECTED CONTROLLERS","",[this]{page="devices";show();});row("PLAYER ORDER","",[this]{page="ports";refresh();});row("BLUETOOTH PAIRING","",[this]{openConsoleControllerBluetooth(mWindow);});row("RESTORE PREVIOUS SETUP","",[this]{mWindow->pushGui(new GuiMsgBox(mWindow,"Restore the protected controller configuration? Games, saves and display settings are kept.","CANCEL",nullptr,"RESTORE",[this]{controllerRestore();refresh();}));});row("DURING A GAME","",[this]{mWindow->pushGui(new GuiMsgBox(mWindow,"RETROARCH GAMES\nPress Hotkey + X (normally SELECT + X) to pause and open Quick Menu.\nControls > Port Controls: change button actions or Mapped Port for player order. Save Game Remap File to keep a game's changes.\n\nStandalone N64 cannot open RetroArch's menu. Set buttons/player order here, then restart that game.\n\nRecovery in the library: hold any button for 8 seconds."));});note("A: select   B: back   Hold any button 8 seconds for recovery.");done();
  }else if(page=="devices"){
   reset("CONNECTED CONTROLLERS");for(int n=0;n<SDL_NumJoysticks();n++){int id=SDL_JoystickGetDeviceInstanceID(n);auto c=InputManager::getInstance()->getInputConfigByDevice(id);if(c)row(c->getDeviceName(),"#"+std::to_string(n+1),[this,id]{selectedDevice=id;page="device";show();});}if(!SDL_NumJoysticks())note("No controller detected. Connect USB or use Bluetooth Pairing.");row("REFRESH","",[this]{show();});done();
  }else if(page=="device"){
   auto c=SDL_JoystickFromInstanceID(selectedDevice)?InputManager::getInstance()->getInputConfigByDevice(selectedDevice):nullptr;reset("CONTROLLER");if(!c){note("Controller disconnected.");}else{note(c->getDeviceName());row("RECONFIGURE BUTTONS","",[this]{setup();});row("TEST INPUTS","",[this]{mWindow->pushGui(new ConsoleControllerTest(mWindow,selectedDevice));});}done();
  }else if(page=="ports"){
   reset("PLAYER ORDER");for(auto&r:data)if(r.size()>3&&r[0]=="PORT"){int port=std::stoi(r[1]);row("PLAYER "+r[1],r[3],[this,port]{selectedPort=port;page="choose";show();});}row("RESTORE AUTOMATIC ORDER","",[this]{action({"automatic"});});note("Applies to the next game launch. Existing per-game overrides still apply.");done();
  }else if(page=="choose"){
   reset("CHOOSE PLAYER "+std::to_string(selectedPort));row("AUTOMATIC","",[this]{page="ports";action({"player",std::to_string(selectedPort),""});});for(auto&r:data)if(r.size()>3&&r[0]=="DEVICE"){auto key=r[1];row(r[3],"#"+std::to_string(std::stoi(r[2])+1),[this,key]{page="ports";action({"player",std::to_string(selectedPort),key});});}done();
  }
 }
 void back(){if(page=="root"){delete this;return;}page=page=="device"?"devices":page=="choose"?"ports":"root";show();}
public:
 ConsoleControllers(Window*w):GuiComponent(w){setSize(Renderer::getScreenWidth(),Renderer::getScreenHeight());refresh();}
 bool ready()const{return !loading;}
 std::string current()const{return page;}
 void update(int dt)override{GuiComponent::update(dt);if(loading&&task.wait_for(std::chrono::milliseconds(0))==std::future_status::ready){auto r=task.get();loading=false;if(!r.first){mWindow->pushGui(new GuiMsgBox(mWindow,r.second));show();return;}auto result=rows(r.second);if(!result.empty()&&(result[0][0]=="DEVICE"||result[0][0]=="PORT"||result[0][0]=="BACKUP")){data=result;show();}else refresh();}}
 bool input(InputConfig*c,Input i)override{if(i.value&&c->isMappedTo("b",i)){back();return true;}if(loading)return true;return menu->input(c,i);}
};
static int controllerRecoveryTime=0;static SDL_JoystickID controllerRecoveryId=-99;static int controllerRecoveryButton=-1;
void controllerRecoveryTick(Window*w,int dt){
 auto top=w->peekGui();if(dynamic_cast<ConsoleControllerRecovery*>(top)||dynamic_cast<ConsoleControllerTrial*>(top)||dynamic_cast<ConsoleSafeControllerWizard*>(top)||dynamic_cast<ConsoleControllerTest*>(top)){controllerRecoveryTime=0;return;}
 SDL_JoystickID found=-99;int button=-1;
 for(int n=0;n<SDL_NumJoysticks()&&found==-99;n++){auto id=SDL_JoystickGetDeviceInstanceID(n);auto joy=SDL_JoystickFromInstanceID(id);if(!joy)continue;for(int b=0;b<SDL_JoystickNumButtons(joy);b++)if(SDL_JoystickGetButton(joy,b)){found=id;button=b;break;}}
 if(found==-99||found!=controllerRecoveryId||button!=controllerRecoveryButton)controllerRecoveryTime=0;else controllerRecoveryTime+=dt;
 controllerRecoveryId=found;controllerRecoveryButton=button;
 if(controllerRecoveryTime>=8000){controllerRecoveryTime=0;w->pushGui(new ConsoleControllerRecovery(w));}
}
