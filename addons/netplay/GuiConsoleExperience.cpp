#include "guis/GuiConsoleSystemSettings.h"
#include "guis/GuiConsoleAchievements.h"
#include "guis/GuiConsoleExperience.h"
#include "guis/GuiMsgBox.h"
#include "FileData.h"
#include "SystemData.h"
#include "views/UIModeController.h"
#include "views/ViewController.h"
#include "Window.h"
#include "Log.h"
#include <unistd.h>
#include <sys/wait.h>
#include <set>
#include <sstream>
#include <algorithm>
#include <cctype>
#include <chrono>
#include <cerrno>
#include <fstream>
#include <cstdlib>
#include <SDL_events.h>
#include "components/ScrollableContainer.h"
#include "views/gamelist/IGameListView.h"

void openConsoleNetplay(Window*,FileData*);

// Read-only details reuse the frontend text renderer, with controller scrolling.
class GuiConsoleDetails : public GuiComponent {
 NinePatchComponent background;
 ScrollableContainer scroll;
 TextComponent text;
public:
 GuiConsoleDetails(Window* window,const std::string& value):GuiComponent(window),background(window,":/frame.png"),scroll(window),text(window) {
  setSize(Renderer::getScreenWidth()*.82f,Renderer::getScreenHeight()*.78f);setPosition(Renderer::getScreenWidth()*.09f,Renderer::getScreenHeight()*.07f);
  addChild(&background);background.fitTo(mSize,Vector3f::Zero(),Vector2f(-24,-24));
  scroll.setPosition(mSize.x()*.04f,mSize.y()*.04f);scroll.setSize(mSize.x()*.92f,mSize.y()*.92f);scroll.setAutoScroll(false);addChild(&scroll);
  text.setFont(Font::get(FONT_SIZE_SMALL));text.setColor(0x555555FF);text.setSize(scroll.getSize().x(),0);text.setText(value);scroll.addChild(&text);
 }
 bool input(InputConfig* config,Input input) override {
  if(input.value && (config->isMappedTo("b",input)||config->isMappedTo("a",input))){delete this;return true;}
  if(input.value && (config->isMappedLike("up",input)||config->isMappedLike("down",input))){auto p=scroll.getScrollPos();p[1]+=config->isMappedLike("up",input)?-60:60;scroll.setScrollPos(p);return true;}
  return true;
 }
 std::vector<HelpPrompt> getHelpPrompts() override {return {{"up/down","scroll"},{"b","back"}};}
 HelpStyle getHelpStyle() override {HelpStyle s;s.position=Vector2f(Renderer::getScreenWidth()*.04f,Renderer::getScreenHeight()*.95f);s.font=Font::get(Renderer::getScreenHeight()*.025f);s.textColor=s.iconColor=0xEEEEEEFF;return s;}
};

bool consoleFeatureEnabled(const std::string& name) {
 return access(("/opt/retropie/configs/all/console-experience/"+name+"-disabled").c_str(),F_OK)!=0;
}

std::string consoleExperienceCommand(const std::vector<std::string>& args, bool& success) {
 success = false;
 int output[2]; if(pipe(output) != 0) return "Could not open helper pipe";
 std::vector<std::string> command = {"/usr/bin/python3", "/usr/local/lib/snes-console/console_experience.py"};
 if(!args.empty() && args[0].compare(0,5,"bios-")==0) {
  command[1]="/usr/local/lib/snes-console/bios_check.py";
  command.push_back(args[0].substr(5));command.insert(command.end(),args.begin()+1,args.end());
 } else if(!args.empty() && args[0].compare(0,5,"game-")==0) {
  command[1]="/usr/local/lib/snes-console/game_settings.py";
  command.push_back(args[0].substr(5));command.insert(command.end(),args.begin()+1,args.end());
 } else if(!args.empty()&&args[0]=="netplay-cancel"){command[1]="/usr/local/lib/snes-console/netplay.py";command.push_back("cancel");} else command.insert(command.end(), args.begin(), args.end());
 std::vector<char*> argv;
 for(auto& part: command) argv.push_back(const_cast<char*>(part.c_str()));
 argv.push_back(nullptr);
 pid_t pid = fork();
 if(pid == 0) {
  close(output[0]); dup2(output[1], STDOUT_FILENO); dup2(output[1], STDERR_FILENO); close(output[1]);
  execv(argv[0], argv.data()); _exit(127);
 }
 close(output[1]);
 if(pid < 0) { close(output[0]); return "Could not start helper"; }
 std::string result; char buffer[1024]; ssize_t size;
 while((size = read(output[0], buffer, sizeof(buffer))) > 0) result.append(buffer, size);
 close(output[0]); int status = 0; while(waitpid(pid, &status, 0) < 0 && errno == EINTR) {}
 success = WIFEXITED(status) && WEXITSTATUS(status) == 0;
 while(!result.empty() && (result.back() == '\n' || result.back() == '\r')) result.pop_back();
 if(success&&!args.empty()&&args[0]=="shader-toggle")LOG(LogInfo)<<"Console shaders toggled: "<<result;
 return result;
}

void openConsoleEmulatorPicker(Window* window, FileData* game) {
 if(game && game->getType() == GAME) window->pushGui(new GuiConsoleEmulatorPicker(window, game->getSourceFileData()));
}

GuiConsoleEmulatorPicker::GuiConsoleEmulatorPicker(Window* window, FileData* game, bool coreOnly, std::function<void()> saved)
 : GuiComponent(window), mCoreOnly(coreOnly), mSaved(saved), mMenu(window, coreOnly?"EMULATOR FOR THIS GAME":"GAME INFORMATION & SETTINGS"), mGame(game) {
 addChild(&mMenu);
 mGameTitle=std::make_shared<TextComponent>(window,"Loading game settings...",Font::get(FONT_SIZE_SMALL),0x555555FF);
 ComponentListRow loading;loading.addElement(mGameTitle,true);mMenu.addRow(loading);
 setSize(mMenu.getSize());setPosition((Renderer::getScreenWidth()-mSize.x())/2,(Renderer::getScreenHeight()-mSize.y())/2);
 const std::string system=game->getSystem()->getName(),path=game->getPath();
 mChoices=std::async(std::launch::async,[system,path,coreOnly] {bool ok;auto data=consoleExperienceCommand({coreOnly?"list":"game-get",system,path},ok);return std::make_pair(ok,data);});
}
void GuiConsoleEmulatorPicker::update(int deltaTime) {
 GuiComponent::update(deltaTime);
 if(mLoading&&++mLoadingFrames>1&&mChoices.wait_for(std::chrono::milliseconds(0))==std::future_status::ready) {
  auto result=mChoices.get();mLoading=false;populate(result.first,result.second);
 }
}
void GuiConsoleEmulatorPicker::populate(bool ok,const std::string& data) {
 auto window=mWindow;auto game=mGame;
 mGameTitle->setText(game->getName());
 if(!mCoreOnly && ok) {
  std::map<std::string,std::string> values;
  std::istringstream lines(data);std::string line;
  while(std::getline(lines,line)){auto tab=line.find('\t');if(tab!=std::string::npos)values[line.substr(0,tab)]=line.substr(tab+1);}
  auto addRow=[this,window](const std::string& label,const std::string& value,std::function<void()> fn) {
   auto text=std::make_shared<TextComponent>(window,value,Font::get(FONT_SIZE_SMALL),0x555555FF);
   ComponentListRow row;row.addElement(std::make_shared<TextComponent>(window,label,Font::get(FONT_SIZE_SMALL),0x555555FF),true);row.addElement(text,false);row.makeAcceptInputHandler(fn);mMenu.addRow(row);return text;
  };
  auto coreText=std::make_shared<std::shared_ptr<TextComponent>>();
  *coreText=addRow("EMULATOR",values["emulator"],[this,coreText]{mWindow->pushGui(new GuiConsoleEmulatorPicker(mWindow,mGame,true,[this,coreText]{bool ok;auto text=consoleExperienceCommand({"game-get",mGame->getSystem()->getName(),mGame->getPath()},ok);std::istringstream lines(text);std::string line;while(std::getline(lines,line))if(line.compare(0,9,"emulator\t")==0)(*coreText)->setText(line.substr(9));}));});
  auto setting=[&,this](std::string label,std::string key,std::vector<std::string> choices) {
   auto value=std::make_shared<std::string>(values[key]);auto text=std::make_shared<std::shared_ptr<TextComponent>>();
   *text=addRow(label,*value,[this,key,choices,value,text]{auto i=std::find(choices.begin(),choices.end(),*value);std::string next=choices[(i==choices.end()?0:(i-choices.begin()+1)%choices.size())];bool ok;auto result=consoleExperienceCommand({"game-set",mGame->getSystem()->getName(),mGame->getPath(),key,next},ok);if(ok){*value=next;(*text)->setText(next);LOG(LogInfo)<<"Console game setting saved: "<<key<<"="<<next;}else mWindow->pushGui(new GuiMsgBox(mWindow,result));});
  };
  {
   setting("CRT SHADER","shader",{"default","on","off"});
   setting("BEZEL","bezel",{"default","off","default_unglazed","ambiance_vintage_tv","ambiance_gameroom","ambiance_monitor_1084s","arcade_1980s","arcade_1980s_vertical","default_curve","default_nocurve"});
   setting("ASPECT RATIO","aspect",{"default","4:3","8:7","16:9","10:9","3:2","3:4"});
   setting("AUTO RESUME","resume",{"default","on","off"});
   addRow("SAVE STATES","View",[this]{bool ok;auto text=consoleExperienceCommand({"game-view",mGame->getSystem()->getName(),mGame->getPath(),"states"},ok);mWindow->pushGui(new GuiConsoleDetails(mWindow,text));});
   addRow("CONTROLLER LAYOUT","View current",[this]{bool ok;auto text=consoleExperienceCommand({"game-view",mGame->getSystem()->getName(),mGame->getPath(),"controllers"},ok);mWindow->pushGui(new GuiConsoleDetails(mWindow,text));});
  }
  addRow("NETPLAY","Host / join",[this]{openConsoleNetplay(mWindow,mGame);});
  addRow("ACHIEVEMENTS","Progress and badges",[this]{openConsoleAchievements(mWindow,mGame);});
  addRow("GAME INFORMATION","View",[this]{std::string text=mGame->getName()+"\n"+mGame->getSystem()->getFullName()+"\n"+mGame->getFileName();for(const auto& key:{"genre","players","developer","publisher","rating","playcount","lastplayed"}){auto value=mGame->metadata.get(key);if(!value.empty())text+="\n"+std::string(key)+": "+value;}auto desc=mGame->metadata.get("desc");if(!desc.empty())text+="\n\n"+desc;mWindow->pushGui(new GuiConsoleDetails(mWindow,text));});
  mMenu.addButton("BACK","return to game list",[this]{delete this;});
  setSize(mMenu.getSize());setPosition((Renderer::getScreenWidth()-mSize.x())/2,(Renderer::getScreenHeight()-mSize.y())/2);
  LOG(LogInfo)<<"Console game settings ready: "<<game->getPath();return;
 }
 std::string selected, systemDefault; std::vector<std::string> cores;
 if(ok) {
  std::istringstream lines(data); std::string line;
  while(std::getline(lines,line)) {
   if(line.compare(0,8,"DEFAULT\t") == 0) systemDefault = line.substr(8);
   else if(line.compare(0,8,"CURRENT\t") == 0) selected = line.substr(8);
   else if(line.compare(0,5,"CORE\t") == 0) cores.push_back(line.substr(5));
  }
 }
 LOG(LogInfo)<<"Console emulator picker: "<<game->getPath()<<" current="<<selected<<" default="<<systemDefault;
 auto add = [this,window](const std::string& label, const std::string& emulator, bool current) {
  ComponentListRow row;
  row.addElement(std::make_shared<TextComponent>(window,(current ? "[CURRENT] " : "")+label,Font::get(FONT_SIZE_MEDIUM),0x555555FF),true);
  row.makeAcceptInputHandler([this,emulator] { save(emulator); }); mMenu.addRow(row,current);
 };
 if(ok) {
  add("SYSTEM DEFAULT ("+systemDefault+")","",selected.empty());
  for(const auto& core: cores) add(core,core,core == selected);
  if(!selected.empty() && std::find(cores.begin(),cores.end(),selected) == cores.end()) {
   ComponentListRow row; row.addElement(std::make_shared<TextComponent>(window,"UNAVAILABLE OVERRIDE: "+selected,Font::get(FONT_SIZE_SMALL),0xAA3333FF),true); mMenu.addRow(row);
  }
 } else {
  ComponentListRow row; row.addElement(std::make_shared<TextComponent>(window,data,Font::get(FONT_SIZE_SMALL),0xAA3333FF),true);mMenu.addRow(row);
 }
 mMenu.addButton("BACK","return to game list",[this] { delete this; });
 setSize(mMenu.getSize());setPosition((Renderer::getScreenWidth()-mSize.x())/2,(Renderer::getScreenHeight()-mSize.y())/2);
}
void GuiConsoleEmulatorPicker::save(const std::string& emulator) {
 bool ok; std::vector<std::string> args = {emulator.empty() ? "default" : "set",mGame->getSystem()->getName(),mGame->getPath()};
 if(!emulator.empty()) args.push_back(emulator);
 std::string result = consoleExperienceCommand(args,ok);
 if(ok) {if(mSaved)mSaved();LOG(LogInfo)<<"Console emulator saved: "<<mGame->getPath()<<" selection="<<(emulator.empty()?"SYSTEM DEFAULT":emulator);delete this;} else mWindow->pushGui(new GuiMsgBox(mWindow,"Could not save emulator:\n"+result));
}
bool GuiConsoleEmulatorPicker::input(InputConfig* config, Input input) {
 if(config->isMappedTo("b",input) && input.value) { delete this;return true; }
 return GuiComponent::input(config,input);
}
std::vector<HelpPrompt> GuiConsoleEmulatorPicker::getHelpPrompts() { return {{"up/down","setting"},{"a",mCoreOnly?"save":"change / view"},{"b","back"}}; }

std::string GuiConsoleSearch::normalize(const std::string& text) {
 std::string value=text;
 const std::vector<std::pair<std::string,std::string>> accents={
  {"é","e"},{"É","e"},{"è","e"},{"ê","e"},{"ë","e"},{"á","a"},{"Á","a"},{"à","a"},{"ä","a"},{"Ä","a"},{"â","a"},
  {"ö","o"},{"Ö","o"},{"ó","o"},{"Ó","o"},{"ô","o"},{"ü","u"},{"Ü","u"},{"ú","u"},{"Ú","u"},{"ñ","n"},{"Ñ","n"},{"ç","c"},{"Ç","c"},{"í","i"},{"Í","i"},{"ï","i"},{"ß","ss"}};
 for(const auto& accent:accents) { size_t pos=0;while((pos=value.find(accent.first,pos))!=std::string::npos) {value.replace(pos,accent.first.size(),accent.second);pos+=accent.second.size();} }
 std::string out;out.reserve(value.size());
 for(unsigned char c:value) if((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')) out.push_back(std::tolower(c));
 return out;
}

GuiConsoleSearch::GuiConsoleSearch(Window* window)
 : GuiComponent(window),mBackground(window,":/frame.png"),mTitle(window),mQueryText(window),mCount(window),mPreviewLabel(window),mResults(window),mPreview(window) {
 auto start=std::chrono::steady_clock::now(); std::set<FileData*> seen;
 for(auto system:SystemData::sSystemVector) {
  if(!system->isGameSystem() || system->isCollection()) continue;
  for(auto file:system->getRootFolder()->getFilesRecursive(GAME)) {
   file=file->getSourceFileData();
   if(!seen.insert(file).second || file->metadata.get("hidden")=="true") continue;
   if(UIModeController::getInstance()->isUIModeKid() && file->metadata.get("kidgame")!="true") continue;
   mIndex.push_back({file,normalize(file->getName()),normalize(file->getFileName())});
  }
 }
 std::sort(mIndex.begin(),mIndex.end(),[](const Entry& a,const Entry& b){return a.title<b.title;});
 LOG(LogInfo)<<"Console search index: "<<mIndex.size()<<" games in "<<std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-start).count()<<" ms";
 setSize(Renderer::getScreenWidth()*.92f,Renderer::getScreenHeight()*.88f);
 setPosition(Renderer::getScreenWidth()*.04f,Renderer::getScreenHeight()*.04f);
 addChild(&mBackground);mBackground.fitTo(mSize,Vector3f::Zero(),Vector2f(-24,-24));
 auto text=[this](TextComponent& c,float y,float h,const std::string& value,float font) {
  c.setFont(Font::get(font));c.setColor(0x555555FF);c.setText(value);c.setPosition(mSize.x()*.03f,mSize.y()*y);c.setSize(mSize.x()*.94f,mSize.y()*h);addChild(&c);
 };
 text(mTitle,.015f,.06f,"SEARCH ALL GAMES",FONT_SIZE_MEDIUM);
 text(mQueryText,.08f,.06f,"",FONT_SIZE_MEDIUM);text(mCount,.145f,.035f,"",FONT_SIZE_SMALL);
 const std::string letters="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
 for(int i=0;i<40;i++) {
  std::string label=i<36?letters.substr(i,1):i==36?"SPACE":i==37?"DEL":i==38?"CLEAR":"RESULTS";
  auto key=std::make_shared<TextComponent>(window,label,Font::get(Renderer::getScreenHeight()*.024f),0x555555FF,ALIGN_CENTER);
  key->setPosition(mSize.x()*(.03f+(i%10)*.094f),mSize.y()*(.20f+(i/10)*.055f));
  key->setSize(mSize.x()*.089f,mSize.y()*.05f);key->setRenderBackground(true);addChild(key.get());mKeys.push_back(key);
 }
 mResults.setFont(Font::get(FONT_SIZE_SMALL));mResults.setColor(0,0x555555FF);mResults.setSelectedColor(0xFFFFFFFF);mResults.setSelectorColor(0x555555FF);mResults.setSelectorColorEnd(0x555555FF);mResults.setUppercase(false);
 mResults.setPosition(mSize.x()*.03f,mSize.y()*.45f);mResults.setSize(mSize.x()*.64f,mSize.y()*.49f);
 mResults.setCursorChangedCallback([this](CursorState){preview();});addChild(&mResults);
 mPreview.setPosition(mSize.x()*.70f,mSize.y()*.45f);mPreview.setMaxSize(mSize.x()*.27f,mSize.y()*.35f);addChild(&mPreview);
 mPreviewLabel.setFont(Font::get(Renderer::getScreenHeight()*.02f));mPreviewLabel.setColor(0x555555FF);mPreviewLabel.setPosition(mSize.x()*.70f,mSize.y()*.82f);mPreviewLabel.setSize(mSize.x()*.27f,mSize.y()*.13f);addChild(&mPreviewLabel);
 refresh();highlight();
}
void GuiConsoleSearch::refresh() {
 auto begin=std::chrono::steady_clock::now(); std::string needle=normalize(mQuery);
 mResults.stopScrolling();mFirstResult=nullptr;mResults.clear();
 if(!needle.empty()) {
  std::vector<std::pair<int,const Entry*>> matches;
  for(const auto& entry:mIndex) {
   auto title=entry.title.find(needle),filename=entry.filename.find(needle);
   if(title!=std::string::npos||filename!=std::string::npos) {
    int rank=entry.title==needle?0:title==0?1:title!=std::string::npos?2:filename==0?3:4;
    matches.push_back({rank,&entry});
   }
  }
  std::stable_sort(matches.begin(),matches.end(),[](const std::pair<int,const Entry*>& a,const std::pair<int,const Entry*>& b){return a.first<b.first;});
  for(const auto& match:matches){auto game=match.second->file;if(!mFirstResult)mFirstResult=game;mResults.add(game->getName()+"  ["+game->getSystem()->getName()+"]",game,0);}
 }

 mQueryText.setText("SEARCH: "+mQuery+"_");
 mCount.setText(needle.empty()?"Use the controller keyboard. Search "+std::to_string(mIndex.size())+" games.":std::to_string(mResults.size())+" matches - DOWN past the keyboard or Y for results");
 if(!mResults.size()) {mKeyboard=true;mPreviewFile=nullptr;mPreview.setImage("");mPreviewLabel.setText("");highlight();}
 preview();mLastQueryMicros=std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now()-begin).count();LOG(LogDebug)<<"Console search query: "<<mResults.size()<<" matches in "<<std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now()-begin).count()<<" us";
}
void GuiConsoleSearch::preview() {
 if(!mResults.size()) return;
 auto game=mResults.getSelected();if(game==mPreviewFile)return;mPreviewFile=game;mPreview.setImage(game->getImagePath());mPreviewLabel.setText(game->getSystem()->getFullName()+"\n"+game->getFileName());
}
void GuiConsoleSearch::highlight() {
 for(size_t i=0;i<mKeys.size();i++) {bool selected=mKeyboard&&int(i)==mKey;mKeys[i]->setBackgroundColor(selected?0x007DCCFF:0xDDDDDDFF);mKeys[i]->setColor(selected?0xFFFFFFFF:0x555555FF);}
 updateHelpPrompts();
}
void GuiConsoleSearch::moveKey(int direction) {
 if(direction==0) mKey=mKey%10==0?mKey+9:mKey-1;
 if(direction==1) mKey=mKey%10==9?mKey-9:mKey+1;
 if(direction==2) mKey=mKey<10?mKey:mKey-10;
 if(direction==3) {if(mKey>=30&&mResults.size()) {mKeyboard=false;mRepeat=-1;} else if(mKey<30)mKey+=10;}
 highlight();
}
void GuiConsoleSearch::erase(){if(!mQuery.empty()){mQuery.pop_back();refresh();}}
void GuiConsoleSearch::activateKey() {
 if(mKey<36 && mQuery.size()<80) mQuery+="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"[mKey];
 else if(mKey==36&&mQuery.size()<80)mQuery+=' ';
 else if(mKey==37){erase();return;}
 else if(mKey==38)mQuery.clear();
 else if(mKey==39){if(mResults.size()){mKeyboard=false;highlight();}return;}
 refresh();
}
bool GuiConsoleSearch::input(InputConfig* config,Input input) {
 if(config->isMappedTo("b",input)&&input.value){delete this;return true;}
 if(config->isMappedTo("x",input)&&input.value){erase();return true;}
 if(config->isMappedTo("y",input)&&input.value){mResults.stopScrolling();mKeyboard=!mKeyboard||!mResults.size();mRepeat=-1;highlight();return true;}
 if(!mKeyboard) {
  if(config->isMappedLike("up",input)&&input.value&&mResults.size() && mResults.getSelected()==mFirstResult){mResults.stopScrolling();mKeyboard=true;highlight();return true;}
  if(config->isMappedTo("a",input)&&input.value&&mResults.size()) {auto game=mResults.getSelected();delete this;ViewController::get()->launch(game);return true;}
  mResults.input(config,input);return true;
 }
 const char* names[]={"left","right","up","down"};
 for(int i=0;i<4;i++) if(config->isMappedLike(names[i],input)) {if(input.value){moveKey(i);mRepeat=mKeyboard?i:-1;mRepeatTime=350;}else mRepeat=-1;return true;}
 if(config->isMappedTo("a",input)&&input.value){activateKey();return true;}
 return true;
}
void GuiConsoleSearch::update(int deltaTime) {
 GuiComponent::update(deltaTime);
 if(mKeyboard&&mRepeat>=0){mRepeatTime-=deltaTime;if(mRepeatTime<=0){moveKey(mRepeat);mRepeatTime=90;}}
}
std::vector<HelpPrompt> GuiConsoleSearch::getHelpPrompts(){return {{"a",mKeyboard?"type":"launch"},{"b","back"},{"x","delete"},{"y","keys / results"}};}

// Finite maintenance-only UI test scripts. No listener, service or input-device changes.
// Normal boots allocate no test controller and expose no automation interface.
void consoleExperienceTestTick(Window* window,int deltaTime) {
 static const char* scriptPath=std::getenv("SNES_EXPERIENCE_TEST_SCRIPT");
 if(!scriptPath) return;
 struct Step {int delay;std::string command;};
 static bool loaded=false;static std::vector<Step> steps;static size_t next=0;static int elapsed=0;
 static std::unique_ptr<InputConfig> config;
 const std::vector<std::string> names={"up","down","left","right","a","b","x","y","start","select","leftshoulder","rightshoulder"};
 if(!loaded) {
  loaded=true;config.reset(new InputConfig(99999,"maintenance test controller","maintenance-only"));
  for(size_t i=0;i<names.size();i++)config->mapInput(names[i],Input(99999,TYPE_BUTTON,int(i),1,true));
  std::ifstream stream(scriptPath);std::string line;
  while(std::getline(stream,line)){std::istringstream row(line);int delay;if(!(row>>delay)||delay<0)continue;std::string rest;std::getline(row,rest);steps.push_back({delay,rest});}
  LOG(LogInfo)<<"CONSOLE_UI_TEST loaded "<<steps.size()<<" steps";
 }
 if(next>=steps.size())return;
 elapsed+=deltaTime;if(elapsed<steps[next].delay)return;elapsed=0;
 std::istringstream row(steps[next++].command);std::string command;row>>command;
 auto button=[&](const std::string& name,int value){auto found=std::find(names.begin(),names.end(),name);if(found!=names.end())window->input(config.get(),Input(99999,TYPE_BUTTON,int(found-names.begin()),value,true));};
 auto tap=[&](const std::string& name){button(name,1);button(name,0);};
 if(command=="BUTTON"){std::string name;int value;row>>name>>value;button(name,value);}
 else if(command=="TAP"){std::string name;row>>name;tap(name);}
 else if(command=="FOCUS") {
  std::string systemName,path;row>>systemName;std::getline(row,path);if(!path.empty())path.erase(0,1);
  for(auto system:SystemData::sSystemVector)if(system->getName()==systemName)for(auto game:system->getRootFolder()->getFilesRecursive(GAME))if(game->getPath()==path){ViewController::get()->goToGameList(system);ViewController::get()->getGameListView(system)->setCursor(game);}
 }
 else if(command=="EXPECT") {
  std::string expected;row>>expected;
  bool pass=consoleSystemSettingsTestState(window,expected.c_str())||consoleAchievementsTestState(window,expected.c_str())||(expected=="HEALTH"&&dynamic_cast<GuiConsoleHealth*>(window->peekGui()))||(expected=="BIOS_WARNING"&&dynamic_cast<GuiConsoleBiosCheck*>(window->peekGui())&&dynamic_cast<GuiConsoleBiosCheck*>(window->peekGui())->mWarning)||(expected=="SETTINGS"&&dynamic_cast<GuiConsoleEmulatorPicker*>(window->peekGui())&&!dynamic_cast<GuiConsoleEmulatorPicker*>(window->peekGui())->mCoreOnly)||(expected=="DETAILS"&&dynamic_cast<GuiConsoleDetails*>(window->peekGui()))||(expected=="SEARCH"&&dynamic_cast<GuiConsoleSearch*>(window->peekGui()))||(expected=="PICKER"&&dynamic_cast<GuiConsoleEmulatorPicker*>(window->peekGui())&&dynamic_cast<GuiConsoleEmulatorPicker*>(window->peekGui())->mCoreOnly)||(expected=="GAMELIST"&&window->peekGui()==ViewController::get()&&ViewController::get()->getState().viewing==ViewController::GAME_LIST);
  LOG(LogInfo)<<"CONSOLE_UI_TEST EXPECT "<<expected<<" "<<(pass?"PASS":"FAIL");
  if(!pass){next=steps.size();SDL_Event event;event.type=SDL_QUIT;SDL_PushEvent(&event);}
 }
 else if(command=="EXPECT_CURSOR") {
  std::string expected;std::getline(row,expected);if(!expected.empty())expected.erase(0,1);
  bool pass=window->peekGui()==ViewController::get()&&ViewController::get()->getState().viewing==ViewController::GAME_LIST&&ViewController::get()->getGameListView(ViewController::get()->getState().getSystem())->getCursor()->getPath()==expected;
  LOG(LogInfo)<<"CONSOLE_UI_TEST CURSOR "<<(pass?"PASS":"FAIL");
  if(!pass){next=steps.size();SDL_Event event;event.type=SDL_QUIT;SDL_PushEvent(&event);}
 }
 else if(command=="TYPE") {
  std::string text;row>>text;auto search=dynamic_cast<GuiConsoleSearch*>(window->peekGui());
  if(search)for(char ch:text){std::string letters="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";size_t target=letters.find(ch);if(target==std::string::npos)continue;while(search->mKey/10<int(target)/10)tap("down");while(search->mKey/10>int(target)/10)tap("up");while(search->mKey%10<int(target)%10)tap("right");while(search->mKey%10>int(target)%10)tap("left");tap("a");}
 }
 else if(command=="STATE") {
  auto search=dynamic_cast<GuiConsoleSearch*>(window->peekGui());auto picker=dynamic_cast<GuiConsoleEmulatorPicker*>(window->peekGui());
  if(search)LOG(LogInfo)<<"CONSOLE_UI_TEST SEARCH index="<<search->mIndex.size()<<" query="<<search->mQuery<<" matches="<<search->mResults.size()<<" query_us="<<search->mLastQueryMicros<<" keyboard="<<search->mKeyboard<<" selected="<<(search->mResults.size()?search->mResults.getSelected()->getPath():std::string("NONE"));
  else if(picker)LOG(LogInfo)<<"CONSOLE_UI_TEST PICKER system="<<picker->mGame->getSystem()->getName()<<" path="<<picker->mGame->getPath();
  else if(window->peekGui()==ViewController::get() && ViewController::get()->getState().viewing==ViewController::GAME_LIST) {
   auto view=ViewController::get()->getGameListView(ViewController::get()->getState().getSystem());LOG(LogInfo)<<"CONSOLE_UI_TEST GAMELIST cursor="<<view->getCursor()->getPath();
  } else LOG(LogInfo)<<"CONSOLE_UI_TEST OTHER";
 }
 else if(command=="BENCH10000") {
  auto search=dynamic_cast<GuiConsoleSearch*>(window->peekGui());
  if(search&&!search->mIndex.empty()) {
   auto saved=search->mIndex;size_t i=0;while(search->mIndex.size()<10000)search->mIndex.push_back(saved[(i++)%saved.size()]);
   search->mQuery="A";search->refresh();LOG(LogInfo)<<"CONSOLE_UI_TEST STRESS index="<<search->mIndex.size()<<" matches="<<search->mResults.size()<<" query_us="<<search->mLastQueryMicros;
   search->mIndex.swap(saved);search->mQuery.clear();search->refresh();
  }
 }
 else if(command=="EXIT"){SDL_Event event;event.type=SDL_QUIT;SDL_PushEvent(&event);}
}

void GuiConsoleSearch::render(const Transform4x4f& parentTrans) {
 GuiComponent::render(parentTrans);
 Renderer::setMatrix(Transform4x4f::Identity());
 Renderer::drawRect(0,Renderer::getScreenHeight()*.92f,Renderer::getScreenWidth(),Renderer::getScreenHeight()*.08f,0x222222FF,0x222222FF);
 mWindow->renderHelpPromptsEarly();
}
HelpStyle GuiConsoleSearch::getHelpStyle() {
 HelpStyle style;style.position=Vector2f(Renderer::getScreenWidth()*.04f,Renderer::getScreenHeight()*.95f);style.origin=Vector2f(0,0);
 style.font=Font::get(Renderer::getScreenHeight()*.025f);style.textColor=0xEEEEEEFF;style.iconColor=0xEEEEEEFF;return style;
}

void GuiConsoleEmulatorPicker::render(const Transform4x4f& parentTrans) {
 GuiComponent::render(parentTrans);
 Renderer::setMatrix(Transform4x4f::Identity());
 Renderer::drawRect(0,Renderer::getScreenHeight()*.92f,Renderer::getScreenWidth(),Renderer::getScreenHeight()*.08f,0x222222FF,0x222222FF);
 mWindow->renderHelpPromptsEarly();
}
HelpStyle GuiConsoleEmulatorPicker::getHelpStyle() {
 HelpStyle style;style.position=Vector2f(Renderer::getScreenWidth()*.04f,Renderer::getScreenHeight()*.95f);style.origin=Vector2f(0,0);
 style.font=Font::get(Renderer::getScreenHeight()*.025f);style.textColor=0xEEEEEEFF;style.iconColor=0xEEEEEEFF;return style;
}

GuiConsoleHealth::GuiConsoleHealth(Window* window):GuiComponent(window),mMenu(window,"SYSTEM HEALTH - BIOS") {
 addChild(&mMenu);mStatus=std::make_shared<TextComponent>(window,"Checking installed systems...",Font::get(FONT_SIZE_SMALL),0x555555FF);
 ComponentListRow row;row.addElement(mStatus,true);mMenu.addRow(row);
 setSize(mMenu.getSize());setPosition((Renderer::getScreenWidth()-mSize.x())/2,Renderer::getScreenHeight()*.08f);
 mCheck=std::async(std::launch::async,[]{bool ok;auto text=consoleExperienceCommand({"bios-dashboard"},ok);return std::make_pair(ok,text);});
}
void GuiConsoleHealth::update(int dt) {
 GuiComponent::update(dt);
 if(!mLoading||mCheck.wait_for(std::chrono::milliseconds(0))!=std::future_status::ready)return;
 auto response=mCheck.get();mLoading=false;
 if(!response.first){mStatus->setText("Check unavailable; B returns. "+response.second);return;}
 std::map<std::string,std::string> detail;
 struct Row {std::string system,label,status,summary;};std::vector<Row> rows;
 std::istringstream lines(response.second);std::string line;std::string seconds;
 while(std::getline(lines,line)) {
  std::istringstream fields(line);std::vector<std::string> parts;std::string part;while(std::getline(fields,part,'\t'))parts.push_back(part);
  if(parts.size()>=5&&parts[0]=="ROW")rows.push_back({parts[1],parts[2],parts[3],parts[4]});
  else if(parts.size()>=2&&parts[0]=="DETAIL")detail[parts[1]]+=(parts.size()>2?parts[2]:"")+std::string("\n");
  else if(parts.size()>1&&parts[0]=="TIME")seconds=parts[1];
 }
 mStatus->setText("BIOS checks only - A details / X rescan ("+seconds+"s)");
 bool first=true;
 for(auto row:rows){
  ComponentListRow r;unsigned int color=(row.status=="MISSING"||row.status=="INCORRECT")?0xAA3333FF:row.status=="READY"?0x236A35FF:0x8C641CFF;
  r.addElement(std::make_shared<TextComponent>(mWindow,row.label,Font::get(FONT_SIZE_SMALL),0x555555FF),true);
  std::string status=row.status=="READY"?(row.summary.find("BIOS found")!=std::string::npos?"BIOS found":"Ready"):row.status=="MISSING"?"BIOS missing":row.status=="INCORRECT"?"Checksum mismatch":row.status=="CONDITIONAL"?"Per-game files":row.status=="OPTIONAL"?"Optional BIOS":row.status=="CHECK"?"Hash unverified":"Not checked";
  r.addElement(std::make_shared<TextComponent>(mWindow,status,Font::get(FONT_SIZE_SMALL),color),false);
  auto text=detail[row.system];r.makeAcceptInputHandler([this,text]{mWindow->pushGui(new GuiConsoleDetails(mWindow,text));});mMenu.addRow(r,first);first=false;
 }
 mMenu.addButton("BACK","return",[this]{delete this;});setSize(mMenu.getSize());setPosition((Renderer::getScreenWidth()-mSize.x())/2,Renderer::getScreenHeight()*.08f);
 LOG(LogInfo)<<"Console BIOS dashboard ready: "<<rows.size()<<" systems in "<<seconds<<" seconds";
}
bool GuiConsoleHealth::input(InputConfig* c,Input i) {
 if(i.value&&c->isMappedTo("b",i)){delete this;return true;}
 if(i.value&&c->isMappedTo("x",i)){auto w=mWindow;delete this;w->pushGui(new GuiConsoleHealth(w));return true;}
 return GuiComponent::input(c,i);
}
std::vector<HelpPrompt> GuiConsoleHealth::getHelpPrompts(){return {{"up/down","system"},{"a","details"},{"x","rescan"},{"b","back"}};}
HelpStyle GuiConsoleHealth::getHelpStyle(){HelpStyle s;s.position=Vector2f(Renderer::getScreenWidth()*.04f,Renderer::getScreenHeight()*.96f);s.font=Font::get(Renderer::getScreenHeight()*.023f);s.textColor=s.iconColor=0xEEEEEEFF;return s;}

GuiConsoleBiosCheck::GuiConsoleBiosCheck(Window* window,FileData* game,std::function<void()> launch):GuiComponent(window),mMenu(window,"BIOS CHECK"),mLaunch(launch) {
 addChild(&mMenu);mStatus=std::make_shared<TextComponent>(window,"Checking required BIOS...",Font::get(FONT_SIZE_SMALL),0x555555FF);
 ComponentListRow row;row.addElement(mStatus,true);mMenu.addRow(row);setSize(mMenu.getSize());setPosition((Renderer::getScreenWidth()-mSize.x())/2,(Renderer::getScreenHeight()-mSize.y())/2);
 game=game->getSourceFileData();std::string system=game->getSystem()->getName(),rom=game->getPath();
 mCheck=std::async(std::launch::async,[system,rom]{bool ok;auto text=consoleExperienceCommand({"bios-check",system,rom},ok);return std::make_pair(ok,text);});
}
void GuiConsoleBiosCheck::update(int dt) {
 GuiComponent::update(dt);
 if(!mLoading||mCheck.wait_for(std::chrono::milliseconds(0))!=std::future_status::ready)return;
 auto response=mCheck.get();mLoading=false;
 if(response.first&&response.second.compare(0,2,"OK")==0){auto launch=mLaunch;delete this;launch();return;}
 mWarning=true;std::string message=response.first?response.second.substr(response.second.find('\n')+1):"BIOS check unavailable: "+response.second+"\nContinue anyway?";
 mMenu.setTitle("BIOS WARNING",Font::get(FONT_SIZE_LARGE));
 std::istringstream body(message);std::string line;bool first=true;
 while(std::getline(body,line)) {
  if(first){mStatus->setText(line);first=false;continue;}
  if(line.empty())continue;
  auto text=std::make_shared<TextComponent>(mWindow,line,Font::get(FONT_SIZE_SMALL),0x555555FF);
  text->setSize(mMenu.getSize().x()-32,0);
  ComponentListRow row;row.addElement(text,true);mMenu.addRow(row);
 }
 mMenu.addButton("CANCEL","return to game list",[this]{LOG(LogInfo)<<"Console BIOS warning cancelled";bool ok;consoleExperienceCommand({"netplay-cancel"},ok);delete this;});
 mMenu.addButton("CONTINUE","launch anyway",[this]{auto launch=mLaunch;LOG(LogInfo)<<"Console BIOS warning continued";delete this;launch();});
 mMenu.setCursorToButtons();setSize(mMenu.getSize());setPosition((Renderer::getScreenWidth()-mSize.x())/2,(Renderer::getScreenHeight()-mSize.y())/2);
 LOG(LogInfo)<<"Console BIOS warning shown: "<<message;
}
bool GuiConsoleBiosCheck::input(InputConfig* c,Input i){if(i.value&&c->isMappedTo("b",i)){LOG(LogInfo)<<"Console BIOS check cancelled";bool ok;consoleExperienceCommand({"netplay-cancel"},ok);delete this;return true;}return GuiComponent::input(c,i);}
std::vector<HelpPrompt> GuiConsoleBiosCheck::getHelpPrompts(){return mLoading?std::vector<HelpPrompt>{{"b","cancel"}}:std::vector<HelpPrompt>{{"left/right","choice"},{"a","select"},{"b","cancel"}};}
HelpStyle GuiConsoleBiosCheck::getHelpStyle(){HelpStyle s;s.position=Vector2f(Renderer::getScreenWidth()*.04f,Renderer::getScreenHeight()*.95f);s.font=Font::get(Renderer::getScreenHeight()*.025f);s.textColor=s.iconColor=0xEEEEEEFF;return s;}
