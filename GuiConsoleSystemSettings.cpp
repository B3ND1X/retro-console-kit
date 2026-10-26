#include "guis/GuiConsoleSystemSettings.h"
#include "guis/GuiConsoleExperience.h"
#include "guis/GuiConsoleAchievements.h"
#include "guis/GuiMsgBox.h"
#include "guis/GuiSettings.h"
#include "components/MenuComponent.h"
#include "components/NinePatchComponent.h"
#include "components/TextComponent.h"
#include "components/SliderComponent.h"
#include "components/ImageComponent.h"
#include "views/ViewController.h"
#include "SystemData.h"
#include "FileData.h"
#include "VolumeControl.h"
#include "Settings.h"
#include "Window.h"
#include "AudioManager.h"
#include "platform.h"
#include <fcntl.h>
#include <SDL_events.h>
#include <SDL_timer.h>
#include <sys/file.h>
#include "Log.h"
#include "InputManager.h"
#include "guis/GuiInputConfig.h"
#include <SDL_joystick.h>
#include <pugixml/src/pugixml.hpp>
#include <future>
#include <thread>
#include <sstream>
#include <map>
#include <fstream>
#include <algorithm>
#include <sys/socket.h>
#include <sys/wait.h>
#include <unistd.h>
#include <cerrno>
#include <cstdlib>
#include <sys/stat.h>
#include <ctime>
void openConsoleControllerBluetooth(Window*);
namespace {
using Result=std::pair<bool,std::string>;
Result command(std::vector<std::string> args,const std::string& secret="") {
 int out[2],in[2];if(pipe(out)||socketpair(AF_UNIX,SOCK_STREAM,0,in))return {false,"ERROR\tCould not open settings helper"};
 std::vector<std::string> cmd={"/usr/bin/sudo","-n","/usr/local/sbin/snes-console-settings"};if(!args.empty()&&args[0]=="bezel-toggle"){cmd={"/usr/bin/python3","/opt/retropie/configs/all/retroarch/overlay/batocera/bezel.py","toggle"};args.clear();}if(!args.empty()&&args[0]=="progress"){cmd={"/usr/bin/python3","/usr/local/lib/snes-console/progress.py"};args.erase(args.begin());}if(!args.empty()&&args[0]=="music"){cmd={"/usr/bin/python3","/usr/local/lib/snes-console/music_control.py"};args.erase(args.begin());}if(!args.empty()&&args[0]=="controllers"){cmd={"/usr/bin/python3","/usr/local/lib/snes-console/controllers.py"};args.erase(args.begin());}if(!args.empty()&&args[0]=="netplay"){cmd={"/usr/bin/python3","/usr/local/lib/snes-console/netplay.py"};args.erase(args.begin());}if(!args.empty()&&args[0]=="software-update"){cmd={"/usr/bin/sudo","-n","/usr/local/sbin/snes-software-update"};args.erase(args.begin());}if(!args.empty()&&args[0]=="media"){cmd={"/usr/bin/python3","/usr/local/lib/snes-console/media.py"};args.erase(args.begin());}if(!args.empty()&&args[0]=="casting"){cmd={"/usr/bin/python3","/usr/local/lib/snes-console/casting/control.py"};args.erase(args.begin());}cmd.insert(cmd.end(),args.begin(),args.end());std::vector<char*> argv;for(auto& s:cmd)argv.push_back(const_cast<char*>(s.c_str()));argv.push_back(nullptr);
 pid_t pid=fork();
 if(pid==0){close(out[0]);close(in[1]);dup2(in[0],STDIN_FILENO);dup2(out[1],STDOUT_FILENO);dup2(out[1],STDERR_FILENO);close(in[0]);close(out[1]);execv(argv[0],argv.data());_exit(127);}
 close(in[0]);close(out[1]);if(pid<0){close(out[0]);close(in[1]);return {false,"ERROR\tCould not start settings helper"};}
 size_t n=0;while(n<secret.size()){ssize_t k=send(in[1],secret.data()+n,secret.size()-n,MSG_NOSIGNAL);if(k<0){if(errno==EINTR)continue;break;}n+=k;}close(in[1]);
 std::string data;char buf[2048];ssize_t k;while((k=read(out[0],buf,sizeof(buf)))>0){if(data.size()<2*1024*1024)data.append(buf,k);}close(out[0]);int status=0;while(waitpid(pid,&status,0)<0&&errno==EINTR){}
 return {WIFEXITED(status)&&WEXITSTATUS(status)==0,data};
}
std::future<Result> start(std::vector<std::string> args,const std::string& secret="") {
 // A packaged-task future does not block B/Back when a bounded web request is pending.
 std::packaged_task<Result()> task([args,secret]{return command(args,secret);});auto future=task.get_future();std::thread(std::move(task)).detach();return future;
}
std::string json(const std::string& value){std::string s="\"";for(unsigned char c:value){if(c=='"'||c=='\\'){s+='\\';s+=c;}else if(c<32)s+=' ';else s+=c;}return s+'"';}
std::vector<std::vector<std::string>> rows(const std::string& data){std::vector<std::vector<std::string>> result;std::istringstream lines(data);std::string line;while(std::getline(lines,line)){std::vector<std::string> r;size_t pos=0,next;while((next=line.find('\t',pos))!=std::string::npos){r.push_back(line.substr(pos,next-pos));pos=next+1;}r.push_back(line.substr(pos));result.push_back(r);}return result;}
HelpStyle style(){HelpStyle s;s.position=Vector2f(Renderer::getScreenWidth()*.04f,Renderer::getScreenHeight()*.95f);s.font=Font::get(Renderer::getScreenHeight()*.024f);s.textColor=s.iconColor=0xEEEEEEFF;return s;}

#include "GuiConsoleControllers.inc"

class ConsoleSettingsKeyboard:public GuiComponent {
 NinePatchComponent background;TextComponent title,value,hint;std::vector<std::shared_ptr<TextComponent>> keys;std::string text,field,characters;int selected=0,repeat=-1,repeatTime=0;bool upper=false,hidden;std::function<void(const std::string&)> saved;
 void refresh(){value.setText(hidden?std::string(text.size(),'*'):(text.size()>62?text.substr(text.size()-62):text));for(size_t i=0;i<keys.size();i++){std::string label;if(i<characters.size()){char c=characters[i];if(upper&&c>='a'&&c<='z')c-=32;label=std::string(1,c);}else{const char* controls[]={"SPACE","DEL","SHIFT","CLEAR","SAVE"};label=controls[i-characters.size()];}keys[i]->setText(label);keys[i]->setBackgroundColor(int(i)==selected?0x007DCCFF:0xDDDDDDFF);keys[i]->setColor(int(i)==selected?0xFFFFFFFF:0x333333FF);}}
 void move(int dir){int step=dir==0?-1:dir==1?1:dir==2?-10:10;selected=(selected+step+int(keys.size()))%int(keys.size());refresh();}
 void activate(){
  if(selected<int(characters.size())){if(text.size()<256){char c=characters[selected];if(upper&&c>='a'&&c<='z')c-=32;text+=c;}}
  else switch(selected-characters.size()){
   case 0:if(text.size()<256)text+=' ';break;
   case 1:if(!text.empty())text.pop_back();break;
   case 2:upper=!upper;break;
   case 3:text.clear();break;
   case 4:{saved(text);delete this;return;}
  }refresh();
 }
public:
 ConsoleSettingsKeyboard(Window* w,const std::string& name,const std::string& key,bool mask,std::function<void(const std::string&)> cb):GuiComponent(w),background(w,":/frame.png"),title(w),value(w),hint(w),text(key),field(key),hidden(mask),saved(cb){
  setSize(Renderer::getScreenWidth()*.92f,Renderer::getScreenHeight()*.86f);setPosition(Renderer::getScreenWidth()*.04f,Renderer::getScreenHeight()*.035f);addChild(&background);background.fitTo(mSize,Vector3f::Zero(),Vector2f(-24,-24));
  auto label=[this](TextComponent& c,float y,const std::string& s,float font){c.setFont(Font::get(font));c.setColor(0x555555FF);c.setText(s);c.setPosition(mSize.x()*.03f,mSize.y()*y);c.setSize(mSize.x()*.94f,mSize.y()*.065f);addChild(&c);};
  label(title,.025f,name,FONT_SIZE_MEDIUM);label(value,.11f,"",FONT_SIZE_MEDIUM);label(hint,.19f,"D-pad: keys   A: type   X: delete   Y: shift   Start: save   B: cancel",FONT_SIZE_SMALL);
  characters="abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()-_=+[]{};:'\",.<>/?\\|`~";
  for(size_t i=0;i<characters.size()+5;i++){auto k=std::make_shared<TextComponent>(w,"",Font::get(Renderer::getScreenHeight()*.022f),0x555555FF,ALIGN_CENTER);k->setPosition(mSize.x()*(.03f+(i%10)*.094f),mSize.y()*(.29f+(i/10)*.075f));k->setSize(mSize.x()*.089f,mSize.y()*.061f);k->setRenderBackground(true);addChild(k.get());keys.push_back(k);}refresh();
 }
 bool input(InputConfig* c,Input i) override {
  if(i.value&&c->isMappedTo("b",i)){delete this;return true;}
  if(i.value&&c->isMappedTo("a",i)){activate();return true;}
  if(i.value&&c->isMappedTo("x",i)){if(!text.empty())text.pop_back();refresh();return true;}
  if(i.value&&c->isMappedTo("y",i)){upper=!upper;refresh();return true;}
  if(i.value&&c->isMappedTo("start",i)){selected=keys.size()-1;activate();return true;}
  const char* names[]={"left","right","up","down"};for(int n=0;n<4;n++)if(c->isMappedLike(names[n],i)){if(i.value){move(n);repeat=n;repeatTime=350;}else repeat=-1;return true;}return true;
 }
 void update(int dt) override{GuiComponent::update(dt);if(repeat>=0){repeatTime-=dt;if(repeatTime<=0){move(repeat);repeatTime=100;}}}
 HelpStyle getHelpStyle() override{return style();}
 std::vector<HelpPrompt> getHelpPrompts() override{return {{"a","type"},{"x","delete"},{"y","shift"},{"start","save"},{"b","cancel"}};}
};


#include "GuiConsoleNetplay.inc"

class ConsoleMusicPlayer:public GuiComponent {
 GuiComponent panel;ImageComponent cover;TextComponent heading,source,title,artist,state,clock,notice;
 std::vector<std::shared_ptr<TextComponent>> buttons;std::vector<std::shared_ptr<ImageComponent>> icons;std::vector<std::string> iconNames;float progress=0;std::future<Result> task;std::map<std::string,std::string> values;
 bool waiting=false,closing=false,tracks=false;int selected=1,pollTime=0;float slide=0;std::string art,queued,queuedValue;
 void query(const std::string& action="status",const std::string& value=""){
  if(waiting){if(action!="status"){queued=action;queuedValue=value;}return;}tracks=action=="tracks";std::vector<std::string> args={"music",action};if(!value.empty())args.push_back(value);task=start(args);waiting=true;
 }
 void refresh(){
  bool spotify=values["ACTIVE_SOURCE"]=="spotify";source.setText(spotify?"SPOTIFY":"LOCAL MUSIC");title.setText(values["TITLE"].empty()?"Your music, ready to play":values["TITLE"]);artist.setText(values["ARTIST"]);state.setText(values["PLAYBACK"]);
  auto timeText=[](float seconds){int n=std::max(0,int(seconds));return std::to_string(n/60)+":"+(n%60<10?"0":"")+std::to_string(n%60);};
  float position=0,duration=0;try{position=std::stof(values["POSITION"]);duration=std::stof(values["DURATION"]);}catch(...){}
  clock.setText(timeText(position)+(duration>0?" / "+timeText(duration):""));
  bool paused=values["PLAYBACK"]!="Playing"&&values["PLAYBACK"]!="Spotify playing";
  std::string repeat=values["REPEAT"].empty()?"all":values["REPEAT"];
  const std::vector<std::string> names={"","","",repeat=="one"?"REPEAT ONE":repeat=="off"?"REPEAT OFF":"REPEAT ALL",values["PLAYER_SHUFFLE"]=="ON"?"SHUFFLE ON":"SHUFFLE OFF",spotify?"END SESSION":"LOCAL TRACKS"};
  const std::vector<std::string> images={"previous",paused?"play":"pause","next",repeat=="one"?"repeat-one":"repeat","shuffle",spotify?"disconnect":"tracks"};
  progress=duration>0?std::max(0.f,std::min(1.f,position/duration)):0;
  for(size_t n=0;n<buttons.size();n++){
   bool focused=int(n)==selected;bool active=(n==3&&repeat!="off")||(n==4&&values["PLAYER_SHUFFLE"]=="ON");
   buttons[n]->setText(names[n]);buttons[n]->setBackgroundColor(focused?0x3FD4B5FF:0x252C36FF);buttons[n]->setColor(focused?0x102327FF:active?0x3FD4B5FF:0xE5EBF2FF);
   icons[n]->setColorShift(focused?0x102327FF:active?0x3FD4B5FF:0xE5EBF2FF);
   if(iconNames[n]!=images[n]){iconNames[n]=images[n];icons[n]->setImage("/usr/local/lib/snes-console/music-player/assets/control-"+images[n]+".svg");}
  }
  if(values["ARTWORK"]!=art){art=values["ARTWORK"];cover.setImage(art.empty()?"/usr/local/lib/snes-console/music-player/assets/cover.svg":art);}
 }
 void activate(){
  if(selected==0)query("previous");else if(selected==1)query("pause");else if(selected==2)query("next");else if(selected==3)query("repeat");else if(selected==4)query("shuffle");
  else if(values["ACTIVE_SOURCE"]=="spotify")query("disconnect");else query("tracks");
 }
 void trackMenu(const Result& result){
  auto menu=new GuiSettings(mWindow,"LOCAL MUSIC");
  for(auto& r:rows(result.second))if(r.size()>2&&r[0]=="TRACK"){
   ComponentListRow entry;auto label=std::make_shared<TextComponent>(mWindow,r[2],Font::get(FONT_SIZE_SMALL),0x555555FF);entry.addElement(label,true);std::string id=r[1];entry.makeAcceptInputHandler([this,menu,id]{query("select",id);delete menu;});menu->addRow(entry);
  }
  mWindow->pushGui(menu);
 }
public:
 ConsoleMusicPlayer(Window* w):GuiComponent(w),panel(w),cover(w),heading(w),source(w),title(w),artist(w),state(w),clock(w),notice(w){
  float sw=Renderer::getScreenWidth(),sh=Renderer::getScreenHeight();setSize(sw,sh);panel.setSize(sw*.38f,sh);panel.setPosition(sw,0);addChild(&panel);
  auto text=[this,sh](TextComponent& t,const std::string& label,float y,float height,float font,unsigned int color){t.setFont(Font::get(sh*font));t.setColor(color);t.setText(label);t.setPosition(panel.getSize().x()*.08f,sh*y);t.setSize(panel.getSize().x()*.84f,sh*height);panel.addChild(&t);};
  text(heading,"MUSIC PLAYER",.035f,.045f,.032f,0xEFF5FAFF);text(source,"LOCAL MUSIC",.09f,.035f,.021f,0x3FD4B5FF);
  cover.setOrigin(.5f,0);cover.setPosition(panel.getSize().x()*.5f,sh*.15f);cover.setMaxSize(panel.getSize().x()*.66f,sh*.40f);cover.setImage("/usr/local/lib/snes-console/music-player/assets/cover.svg");panel.addChild(&cover);
  text(title,"Loading music...",.57f,.075f,.028f,0xF3F6FAFF);text(artist,"",.65f,.035f,.021f,0xA9B7C6FF);text(state,"",.695f,.03f,.019f,0xA9B7C6FF);text(clock,"",.73f,.028f,.018f,0xA9B7C6FF);
  float pw=panel.getSize().x();
  for(int n=0;n<6;n++){
   auto button=std::make_shared<TextComponent>(w,"",Font::get(sh*(n<3?.022f:.018f)),0xE5EBF2FF,ALIGN_CENTER);
   float x=n<3?.08f+(n%3)*.285f:n<5?.08f+(n-3)*.43f:.08f;float y=n<3?.80f:n<5?.875f:.94f;float width=n<3?.27f:n<5?.41f:.84f;
   button->setPosition(pw*x,sh*y);button->setSize(pw*width,sh*.05f);button->setRenderBackground(true);panel.addChild(button.get());buttons.push_back(button);
   auto icon=std::make_shared<ImageComponent>(w);icon->setOrigin(.5f,.5f);icon->setPosition(pw*(x+(n<3?width*.5f:width*.14f)),sh*(y+.025f));icon->setResize(sh*(n<3?.033f:.026f),sh*(n<3?.033f:.026f));panel.addChild(icon.get());icons.push_back(icon);iconNames.push_back("");
  }
  text(notice,"",.125f,.025f,.016f,0xE5B181FF);refresh();query();
 }
 bool ready()const{return values.count("PLAYBACK")&&slide>=1&&!closing;}
 std::string value(const std::string& key)const{auto it=values.find(key);return it==values.end()?"":it->second;}
 bool input(InputConfig* config,Input input)override{
  if(!input.value)return true;
  if(config->isMappedTo("b",input)){closing=true;return true;}
  if(closing)return true;
  if(config->isMappedLike("left",input)){selected=selected<3?(selected+2)%3:selected<5?7-selected:5;refresh();}
  else if(config->isMappedLike("right",input)){selected=selected<3?(selected+1)%3:selected<5?7-selected:5;refresh();}
  else if(config->isMappedLike("down",input)){selected=selected<3?3:selected<5?5:1;refresh();}
  else if(config->isMappedLike("up",input)){selected=selected==5?3:selected>=3?1:5;refresh();}
  else if(config->isMappedTo("a",input))activate();
  else if(config->isMappedTo("leftshoulder",input))query("previous");
  else if(config->isMappedTo("rightshoulder",input))query("next");
  return true;
 }
 void update(int dt)override{
  slide=std::max(0.f,std::min(1.f,slide+(closing?-1.f:1.f)*dt/220.f));
  if(closing&&slide<=0){delete this;return;}
  panel.setPosition(Renderer::getScreenWidth()-panel.getSize().x()+(1-slide)*(1-slide)*panel.getSize().x(),0);GuiComponent::update(dt);
  if(waiting&&task.wait_for(std::chrono::milliseconds(0))==std::future_status::ready){auto result=task.get();waiting=false;
   if(tracks){tracks=false;if(result.first)trackMenu(result);else notice.setText("Could not load tracks.");}
   else{if(result.first){values.clear();for(auto& r:rows(result.second))if(r.size()>1)values[r[0]]=r[1];notice.setText(values["NOTE"]);refresh();}else notice.setText("Music is not ready. Try again.");}
  }
  if(!queued.empty()&&!waiting&&!closing){auto action=queued,value=queuedValue;queued.clear();queuedValue.clear();query(action,value);}
  pollTime+=dt;if(pollTime>=1000&&!waiting&&!closing){pollTime=0;query();}
 }
 void render(const Transform4x4f& parent)override{
  Renderer::setMatrix(parent);Renderer::drawRect(0,0,Renderer::getScreenWidth(),Renderer::getScreenHeight(),0x00000088,0x00000088);
  Renderer::drawRect(panel.getPosition().x(),0,panel.getSize().x(),panel.getSize().y(),0x141A23FF,0x141A23FF);
  float x=panel.getPosition().x()+panel.getSize().x()*.08f,y=Renderer::getScreenHeight()*.773f,width=panel.getSize().x()*.84f,height=std::max(2.f,Renderer::getScreenHeight()*.003f);
  Renderer::drawRect(x,y,width,height,0x34414EFF,0x34414EFF);if(progress>0)Renderer::drawRect(x,y,width*progress,height,0x3FD4B5FF,0x3FD4B5FF);
  GuiComponent::render(parent);
 }
 HelpStyle getHelpStyle()override{return style();}
 std::vector<HelpPrompt> getHelpPrompts()override{return {{"a","select"},{"b","close"}};}
};

// Passive overlay: never joins the GUI stack or handles controller input.
class ConsoleSongBanner:public GuiComponent {
 ImageComponent background,art;TextComponent caption,title,artist;
 std::string lastId,artPath;int age=5000,poll=1000;float previousPosition=0;bool playing=false;
public:
 ConsoleSongBanner(Window* w):GuiComponent(w),background(w),art(w),caption(w),title(w),artist(w){
  float sw=Renderer::getScreenWidth(),sh=Renderer::getScreenHeight(),width=sw*.34f,height=sh*.096f;
  setSize(width,height);background.setImage("/usr/local/lib/snes-console/music-player/assets/banner-bg.svg");background.setResize(width,height);addChild(&background);
  float pad=height*.13f,side=height*.70f;art.setOrigin(.5f,.5f);art.setPosition(pad+side*.5f,pad+side*.5f);art.setMaxSize(side,side);art.setImage("/usr/local/lib/snes-console/music-player/assets/music-note.svg");addChild(&art);
  auto text=[this,width,height,pad,side](TextComponent& t,float y,float h,float font,unsigned color){t.setPosition(side+pad*2,height*y);t.setSize(width-side-pad*3,height*h);t.setFont(Font::get(height*font));t.setColor(color);addChild(&t);};
  text(caption,.09f,.20f,.145f,0x3FD4B5FF);text(title,.32f,.31f,.235f,0xF0F5FAFF);text(artist,.66f,.22f,.17f,0xACBAC9FF);
 }
 bool visible()const{return playing&&age<4400&&!Settings::getInstance()->getBool("MusicSongTitlesDisabled");}
 bool hasArtwork()const{return !artPath.empty();}
 void update(int dt)override{
  age=std::min(6000,age+dt);poll+=dt;
  if(poll<500)return;poll=0;
  const char* fixture=std::getenv("SNES_MUSIC_NOW_PLAYING");std::string file=fixture?fixture:"/dev/shm/snes-music-"+std::to_string(getuid())+".tsv";
  struct stat info;if(stat(file.c_str(),&info)!=0||std::time(nullptr)-info.st_mtime>5||info.st_size>16384){playing=false;return;}
  std::ifstream stream(file);std::string payload((std::istreambuf_iterator<char>(stream)),std::istreambuf_iterator<char>());std::map<std::string,std::string> value;
  for(auto& row:rows(payload))if(row.size()>1)value[row[0]]=row[1];
  bool now=value["PLAYING"]=="1"&&!value["ID"].empty()&&!value["TITLE"].empty();float position=0;try{position=std::stof(value["POSITION"]);}catch(...){}
  bool restart=now&&playing&&position<2&&previousPosition>5;
  if(now){
   if(lastId!=value["ID"]||restart){lastId=value["ID"];age=Settings::getInstance()->getBool("MusicSongTitlesDisabled")?5000:0;}
   caption.setText(value["SOURCE"]=="spotify"?"NOW PLAYING  /  SPOTIFY":"NOW PLAYING  /  LOCAL MUSIC");title.setText(value["TITLE"]);artist.setText(value["ARTIST"]);
   std::string image=value["ARTWORK"];if(!image.empty()&&access(image.c_str(),R_OK)!=0)image.clear();
   if(image!=artPath||art.getSize().x()==0){artPath=image;art.setImage(image.empty()?"/usr/local/lib/snes-console/music-player/assets/music-note.svg":image);}
  }
  playing=now;previousPosition=position;
 }
 void render(const Transform4x4f& parent)override{
  if(!visible())return;float alpha=std::min(1.f,age/350.f)*std::min(1.f,(4400-age)/600.f);setOpacity(static_cast<unsigned char>(std::max(0.f,alpha)*255));
  setPosition((Renderer::getScreenWidth()-getSize().x())*.5f,Renderer::getScreenHeight()*.025f-(1-alpha)*8);GuiComponent::render(parent);
 }
};
std::unique_ptr<ConsoleSongBanner> songBanner;

class MusicSlider:public SliderComponent {
 std::function<void()> release;
public:
 bool focused=false;
 MusicSlider(Window* w):SliderComponent(w,0.f,100.f,5.f,"%"){}
 bool input(InputConfig* c,Input i) override {
  bool handled=SliderComponent::input(c,i);
  if(handled&&i.value){auto config=std::make_shared<InputConfig>(*c);release=[this,config,i]()mutable{i.value=0;SliderComponent::input(config.get(),i);};}
  if(!i.value)release=nullptr;
  // The same hat's neutral event must also reach ComponentList to stop scrolling.
  return i.value?handled:false;
 }
 void onFocusGained() override{focused=true;SliderComponent::onFocusGained();}
 void onFocusLost() override{focused=false;if(release)release();release=nullptr;SliderComponent::onFocusLost();}
};

#include "GuiConsoleSoftwareUpdates.inc"

#include "GuiConsoleMedia.inc"
#include "GuiConsoleCasting.inc"

class ConsoleSettings:public GuiComponent {
 std::unique_ptr<MenuComponent> menu;std::future<Result> task;std::future<Result> musicStatusTask;bool musicStatusPending=false;int musicStatusTime=0;std::shared_ptr<TextComponent> musicStatusText,musicTitleText;std::shared_ptr<MusicSlider> musicVolumeSlider;std::string musicPlayback,musicTitle,musicActiveSource="local";std::string musicSource="local";std::string page="root",pending,secret,payload,version,saveSystem="all";bool saveStates=false;bool loading=false,change=false,refresh=false;int remembered=0;
 void reset(const std::string& title){if(menu)removeChild(menu.get());menu.reset(new MenuComponent(mWindow,title.c_str()));addChild(menu.get());}
 void position(){setSize(menu->getSize());setPosition((Renderer::getScreenWidth()-mSize.x())/2,(Renderer::getScreenHeight()-mSize.y())/2);}
 void row(const std::string& name,const std::string& value="",std::function<void()> cb=nullptr){ComponentListRow r;auto t=std::make_shared<TextComponent>(mWindow,name,Font::get(FONT_SIZE_SMALL),0x555555FF);t->setSize(Renderer::getScreenHeight()*.60f,0);r.addElement(t,true);if(!value.empty()){auto v=std::make_shared<TextComponent>(mWindow,value,Font::get(FONT_SIZE_SMALL),0x3377AAFF);v->setSize(Renderer::getScreenHeight()*.28f,0);r.addElement(v,false);}if(cb)r.makeAcceptInputHandler(cb);menu->addRow(r);}
 void note(const std::string& s){ComponentListRow r;auto t=std::make_shared<TextComponent>(mWindow,s,Font::get(FONT_SIZE_SMALL),0x666666FF);t->setSize(Renderer::getScreenHeight()*.91f,0);r.addElement(t,true);menu->addRow(r);}
 void done(){menu->addButton("BACK","return",[this]{back();});position();LOG(LogInfo)<<"Console system settings ready: "<<page;}
 void request(const std::string& next,const std::string& data=""){pending=next;payload=data;change=true;}
 void action(const std::string& action,const std::string& data){request(action,data);}
 void keyboard(const std::string& title,bool hidden,std::function<void(const std::string&)> cb){mWindow->pushGui(new ConsoleSettingsKeyboard(mWindow,title,"",hidden,cb));}
 void join(const std::string& ssid,bool open=false){
  auto confirm=[this,ssid](const std::string& password){mWindow->pushGui(new GuiMsgBox(mWindow,"Connect to "+ssid+"? Wi-Fi may briefly disconnect. If the connection fails, the previous network will be restored.","CANCEL",nullptr,"CONNECT",[this,ssid,password]{action("wifi-join","{\"ssid\":"+json(ssid)+",\"password\":"+json(password)+"}");}));};
  if(open)confirm("");else keyboard("WI-FI PASSWORD (HIDDEN)",true,confirm);
 }
 void statsToggle(){row("DEVICE STATS OVERLAY",Settings::getInstance()->getBool("ConsoleDeviceStats")?"ON":"OFF",[this]{Settings::getInstance()->setBool("ConsoleDeviceStats",!Settings::getInstance()->getBool("ConsoleDeviceStats"));Settings::getInstance()->saveFile();request(page);});}
 void root(){page="root";reset("SETTINGS");
  row("NETWORK & WI-FI","",[this]{request("network");});
  row("CONTROLLER MANAGER","",[this]{mWindow->pushGui(new ConsoleControllers(mWindow));});
  row("AUDIO","",[this]{request("audio");});
  row("CASTING & AIRPLAY","",[this]{mWindow->pushGui(new ConsoleCasting(mWindow));});
  row("MUSIC","",[this]{request("music");});
  row("NETPLAY","",[this]{mWindow->pushGui(new ConsoleNetplay(mWindow));});
  row("RETROACHIEVEMENTS","",[this]{openConsoleAchievements(mWindow);});
  row("SOFTWARE UPDATES","",[this]{mWindow->pushGui(new ConsoleSoftwareUpdates(mWindow));});
  row("SAVE BACKUPS","",[this]{request("saves");});done();
 }
 void video(){page="video";reset("DISPLAY & EFFECTS");note("DISPLAY: 1920 x 1080 at 60 Hz");
  row("MENU ANIMATION",Settings::getInstance()->getString("TransitionStyle"),[this]{mWindow->pushGui(new GuiMsgBox(mWindow,"Choose a menu animation. Instant uses the fewest resources.","INSTANT",[this]{Settings::getInstance()->setString("TransitionStyle","instant");Settings::getInstance()->saveFile();request("video");},"SLIDE",[this]{Settings::getInstance()->setString("TransitionStyle","slide");Settings::getInstance()->saveFile();request("video");},"FADE",[this]{Settings::getInstance()->setString("TransitionStyle","fade");Settings::getInstance()->saveFile();request("video");}));});
  bool off=access("/opt/retropie/configs/all/console-experience/shaders-disabled",F_OK)==0;
  row("CRT SHADERS",off?"OFF":"ON",[this]{bool ok;auto r=consoleExperienceCommand({"shader-toggle"},ok);if(ok)request("video");else mWindow->pushGui(new GuiMsgBox(mWindow,r));});
  std::ifstream state("/opt/retropie/configs/all/retroarch/overlay/batocera/settings.json");std::string stateText((std::istreambuf_iterator<char>(state)),std::istreambuf_iterator<char>());auto at=stateText.find("\"enabled\"");bool bezelOn=at!=std::string::npos&&stateText.substr(at,stateText.find(',',at)-at).find("true")!=std::string::npos;
  row("BEZELS",bezelOn?"ON":"OFF",[this]{action("bezel-toggle","");});
  note("Hold X on a highlighted game for its aspect ratio and individual display effects.");done();
 }

 void saveConfirm(const std::string& system,bool states){
  saveSystem=system;saveStates=states;
  mWindow->pushGui(new GuiMsgBox(mWindow,"Restore "+system+" progress from "+version.substr(0,15)+" UTC?\n"+(states?"Includes SAVE STATES. These require the same emulator version.\n":"Battery saves only; current save states will be kept.\n")+"Your current progress will be protected by Undo Restore. Games and settings are untouched.","CANCEL",nullptr,"RESTORE",[this]{request("saves-restore");}));
 }
 void savePopulate(const Result& result){
  reset(page=="saves-versions"?"DATED SAVE BACKUPS":page=="saves-inspect"?"RESTORE PROGRESS":"SAVE BACKUPS");
  if(!result.first){for(auto& r:rows(result.second))if(r.size()>1)note(r[1]);row("TRY AGAIN","",[this]{request(page);});done();return;}
  std::string target="network",automatic="OFF",undo="NONE";
  for(auto& r:rows(result.second)){
   if(r.size()<2)continue;
   if(r[0]=="CHOICE"&&r.size()>2){auto key=r[1];row(r[2],"SELECT",[this,key]{request("saves-target",key);});}
   else if(r[0]=="DESTINATION")target=r[1];else if(r[0]=="AUTOMATIC")automatic=r[1];else if(r[0]=="UNDO")undo=r[1];
   else if(r[0]=="VERSION"){auto v=r[1];row(r.size()>2?r[2]:v,"VIEW",[this,v]{version=v;request("saves-inspect");});}
   else if(r[0]=="SYSTEM"&&r.size()>2){auto system=r[1];row(system,r[2]+" files",[this,system]{saveConfirm(system,false);});}
   else if(r[0]=="COUNT")note(r[1]+" progress files in this version");
   else if(r[0]=="PROGRESS"||r[0]=="LAST"||r[0]=="NOTE")note(r[1]);
  }
  if(page=="saves"){
   row("BACK UP NOW","",[this]{request("saves-backup");});
   row("RESTORE A DATED VERSION","",[this]{request("saves-versions");});
   row("DESTINATION",target=="share"?"NETWORK SHARE":target=="export"?"SSH / SFTP EXPORT":"USB DRIVE",[this]{request("saves-destinations");});
   if(undo=="AVAILABLE")row("UNDO LAST RESTORE","",[this]{mWindow->pushGui(new GuiMsgBox(mWindow,"Replace current progress with the safety copy made before the last restore?", "CANCEL",nullptr,"UNDO RESTORE",[this]{request("saves-undo");}));});
   note("Manual backups only. Exit games, choose a destination, then Back Up Now. Versions remain until you remove them.");
  }else if(page=="saves-destinations"){
   note("USB writes to an attached drive. Network Share uses an already mounted local share. SSH / SFTP Export prepares files for manual download from this Pi.");
  }else if(page=="saves-inspect"){
   row("RESTORE ALL BATTERY SAVES","",[this]{saveConfirm("all",false);});
   row("RESTORE ALL SAVES + STATES","",[this]{saveConfirm("all",true);});
  }else if(page=="saves-versions"){
   if(result.second.empty())note("No dated versions at this destination yet. Choose Back Up Now first.");
  }else row("CONTINUE","",[this]{request("saves");});
  done();
 }
 void musicDetails(){
  std::string text="NOW PLAYING\n"+(musicTitle.empty()?"No track":musicTitle)+"\n\n"+musicPlayback;
  if(musicActiveSource=="spotify")mWindow->pushGui(new GuiMsgBox(mWindow,text+"\n\nChoose tracks, Play/Pause and Skip in the Spotify app. Pausing stays quiet until the session ends.","END SPOTIFY SESSION",[this]{request("music-disconnect");},"BACK",nullptr));
  else mWindow->pushGui(new GuiMsgBox(mWindow,text,"PLAY / PAUSE",[this]{request("music-pause");},"NEXT TRACK",[this]{request("music-next");},"BACK",nullptr));
 }
 std::shared_ptr<TextComponent> musicText(const std::string& text,bool details){
  ComponentListRow r;auto font=Font::get(FONT_SIZE_SMALL);auto t=std::make_shared<TextComponent>(mWindow,text,font,0x666666FF);t->setSize(Renderer::getScreenHeight()*.91f,font->getHeight());r.addElement(t,true);if(details)r.makeAcceptInputHandler([this]{musicDetails();});menu->addRow(r);return t;
 }
 void musicPoll(int dt){
  if(musicStatusPending&&musicStatusTask.wait_for(std::chrono::milliseconds(0))==std::future_status::ready){
   auto r=musicStatusTask.get();musicStatusPending=false;
   if(r.first&&page=="music"&&!loading&&!change&&musicStatusText&&musicTitleText){
    for(auto& v:rows(r.second))if(v.size()>1){if(v[0]=="PLAYBACK")musicPlayback=v[1];if(v[0]=="TITLE")musicTitle=v[1];if(v[0]=="ACTIVE_SOURCE")musicActiveSource=v[1];}
    musicStatusText->setText("STATUS: "+musicPlayback);musicTitleText->setText("NOW PLAYING: "+(musicTitle.empty()?"No track":musicTitle));
   }
  }
  if(page!="music"||loading||change)return;
  musicStatusTime+=dt;if(musicStatusTime>=2000&&!musicStatusPending){musicStatusTime=0;musicStatusTask=start({"music","status"});musicStatusPending=true;}
 }
 void musicPopulate(const Result& result){
  reset(page=="music-tracks"?"CHOOSE LOCAL MUSIC":"MUSIC");
  if(!result.first){for(auto& r:rows(result.second))if(r.size()>1)note(r[1]);row("RETURN TO MUSIC","",[this]{request("music");});done();return;}
  if(page=="music-tracks"){
   for(auto& r:rows(result.second)){if(r.size()>2&&r[0]=="TRACK"){auto id=r[1];row(r[2],"",[this,id]{request("music-select",id);});}else if(r.size()>1&&r[0]=="NOTE")note(r[1]);}
   done();return;
  }
  page="music";
  std::map<std::string,std::string> values;for(auto& r:rows(result.second))if(r.size()>1)values[r[0]]=r[1];
  musicSource=values["SOURCE"];musicActiveSource=values["ACTIVE_SOURCE"].empty()?musicSource:values["ACTIVE_SOURCE"];
  row("MUSIC",values["ENABLED"],[this]{request("music-enabled");});
  row("DEFAULT SOURCE",values["SOURCE"]=="spotify"?"SPOTIFY ONLY":"LOCAL MUSIC",[this]{mWindow->pushGui(new GuiMsgBox(mWindow,"Local is the default: Spotify can temporarily take over, then local music returns when that session ends. Pausing Spotify stays quiet. Spotify Only never plays local music.","LOCAL DEFAULT",[this]{request("music-source","local");},"SPOTIFY ONLY",[this]{request("music-source","spotify");},"CANCEL",nullptr));});
  auto volume=std::make_shared<MusicSlider>(mWindow);musicVolumeSlider=volume;try{volume->setValue(std::stoi(values["VOLUME"]));}catch(...){}
  ComponentListRow vr;vr.addElement(std::make_shared<TextComponent>(mWindow,"MUSIC VOLUME",Font::get(FONT_SIZE_SMALL),0x555555FF),true);vr.addElement(volume,true);menu->addRow(vr);
  menu->addButton("SAVE VOLUME","save",[this,volume]{request("music-volume",std::to_string(int(volume->getValue())));});
  row("DISPLAY SONG TITLES",Settings::getInstance()->getBool("MusicSongTitlesDisabled")?"OFF":"ON",[this]{Settings::getInstance()->setBool("MusicSongTitlesDisabled",!Settings::getInstance()->getBool("MusicSongTitlesDisabled"));Settings::getInstance()->saveFile();request("music");});
  row("OPEN MUSIC PLAYER","",[this]{openConsoleMusicPlayer(mWindow);});
  if(values["SOURCE"]=="spotify")row("DISCONNECT / FORGET ACCOUNT","",[this]{mWindow->pushGui(new GuiMsgBox(mWindow,"Forget the Spotify account stored on this console?","CANCEL",nullptr,"FORGET",[this]{request("music-forget");}));});
  row("MUSIC CREDITS","",[this]{mWindow->pushGui(new GuiMsgBox(mWindow,"Official Batocera soundtrack: Bolt Action and Nihilore.\nBolt Action: non-commercial use with artist/song credit. boltactionmusic.wixsite.com/home\nNihilore: Creative Commons Attribution 4.0. nihilore.com\nOriginal licence files and song credits are in RetroPie/music. Music files are unchanged."));});
  row("FADE MUSIC",values["FADE"],[this]{request("music-fade");});
  row("MUSIC DURING GAMES",values["DURING_GAMES"],[this]{request("music-during_games");});
  note("Music volume affects music only. During Games OFF stops music before launch. Spotify may need Play again after returning from a game.");
  if(!values["NOTE"].empty())note(values["NOTE"]);
  row("REFRESH STATUS","",[this]{request("music");});done();
 }
 void populate(const Result& result){
  if(page.find("music")==0){musicPopulate(result);return;}
  if(page.find("saves")==0){savePopulate(result);return;}
  if(page=="wifi-join"||page=="bluetooth-pair"||page=="audio-select"||page=="audio-store"||page=="bezel-toggle"){
   std::string message;for(auto& r:rows(result.second))if(r.size()>1){if(r[0]=="MIXER"&&result.first){Settings::getInstance()->setString("AudioCard","default");Settings::getInstance()->setString("AudioDevice",r[1]);Settings::getInstance()->saveFile();}else message+=r[1]+"\n";}
   std::string next=page=="wifi-join"?"network":page=="bluetooth-pair"?"bluetooth":page=="bezel-toggle"?"video":"audio";
   reset("SETTINGS");note(message.empty()?(result.first?"Setting saved.":"The operation could not be completed."):message);row("CONTINUE","",[this,next]{request(next);});done();return;
  }
  reset(page=="network"?"NETWORK & WI-FI":page=="wifi-scan"?"CHOOSE WI-FI NETWORK":page.find("bluetooth")==0?"BLUETOOTH CONTROLLERS":page=="audio"?"AUDIO":page=="updates"?"SOFTWARE UPDATE CHECK":"DEVICE INFO & HEALTH");
  if(!result.first)note("Could not load this setting. Press B to go back and try again.");
  for(auto& r:rows(result.second)){
   if(r.empty())continue;
   if(r[0]=="NETWORK"&&r.size()>3){auto ssid=r[1],security=r[3];row(ssid,security,[this,ssid,security]{if(security=="Unsupported security")mWindow->pushGui(new GuiMsgBox(mWindow,"This network needs enterprise, WPA3-only or legacy security setup. Choose a WPA2 personal network."));else join(ssid,security=="Open");});}
   else if(r[0]=="DEVICE"&&r.size()>3){auto address=r[1],name=r[2];row(name,r[3],[this,address,name]{mWindow->pushGui(new GuiMsgBox(mWindow,"Pair or reconnect "+name+"? Put it in pairing mode first. Existing controllers will stay paired.","CANCEL",nullptr,"CONNECT",[this,address]{action("bluetooth-pair","{\"address\":"+json(address)+"}");}));});}
   else if(r[0]=="OUTPUT"&&r.size()>3){auto card=r[1],name=r[3];row(name,"SELECT",[this,card,name]{mWindow->pushGui(new GuiMsgBox(mWindow,"Use "+name+" for audio? Restart EmulationStation afterwards to apply it.","CANCEL",nullptr,"USE OUTPUT",[this,card]{action("audio-select","{\"card\":"+json(card)+"}");}));});}
   else if(r.size()>1){if(r[0]=="NOTE"||r[0]=="ERROR"||r[0]=="STATUS"||r[0]=="INFO")note(r[1]);else row(r[0],r[1]);}
  }
  if(page=="network"){row("CHOOSE WI-FI NETWORK","",[this]{request("wifi-scan");});row("ENTER NETWORK NAME","",[this]{keyboard("WI-FI NETWORK NAME",false,[this](const std::string& ssid){if(!ssid.empty())join(ssid);});});row("REFRESH STATUS","",[this]{request("network");});}
  if(page=="info"){statsToggle();row("REFRESH DEVICE INFO","",[this]{request("info");});}
  if(page=="wifi-scan")row("SCAN AGAIN","",[this]{request("wifi-scan");});
  if(page.find("bluetooth")==0)row("SCAN FOR CONTROLLERS","",[this]{request("bluetooth-scan");});
  if(page=="audio"){
   auto slider=std::make_shared<SliderComponent>(mWindow,0.f,100.f,5.f,"%");slider->setValue(VolumeControl::getInstance()->getVolume());ComponentListRow r;r.addElement(std::make_shared<TextComponent>(mWindow,"VOLUME",Font::get(FONT_SIZE_SMALL),0x555555FF),true);r.addElement(slider,true);menu->addRow(r);
   menu->addButton("SAVE VOLUME","save",[this,slider]{VolumeControl::getInstance()->setVolume(int(slider->getValue()));action("audio-store","");});note("Select Volume, then use Left / Right. Choose Save Volume to apply. USB audio outputs appear when connected.");
  }
  done();
 }
 bool fromControllerManager=false,fromMainDeveloperTools=false;
 void back(){if(fromMainDeveloperTools&&(page=="video"||page=="info")){delete this;return;}if(fromControllerManager&&page=="bluetooth"){delete this;return;}if(page=="root"){delete this;return;}request(page.find("bluetooth-")==0?"bluetooth":page.find("music-")==0?"music":page=="wifi-scan"?"network":page=="saves-inspect"?"saves-versions":page.find("saves-")==0?"saves":"root");}
public:
 ConsoleSettings(Window* w,bool bluetooth=false,const std::string& developerPage=""):GuiComponent(w){root();if(bluetooth){fromControllerManager=true;request("bluetooth");}if(!developerPage.empty()){fromMainDeveloperTools=true;request(developerPage);}}
 bool ready() const{return !loading&&!change;}
 std::string current() const{return page;}
 std::string source() const{return musicSource;}
 bool volumeFocused()const{return musicVolumeSlider&&musicVolumeSlider->focused;}
 float musicVolume()const{return musicVolumeSlider?musicVolumeSlider->getValue():-1;}
 void update(int dt) override{
  GuiComponent::update(dt);
  if(change){change=false;page=pending;loading=false;if(page=="root")root();else if(page=="video")video();else{reset("SETTINGS");note(page=="wifi-join"?"Connecting to Wi-Fi... Previous settings will be restored if it fails.":page=="bluetooth-scan"?"Scanning for controllers... Put the controller in pairing mode.":page=="bluetooth-pair"?"Pairing controller...":"Loading...");position();if(page.find("saves")==0){
    std::string op=page=="saves"?"status":page.substr(6);std::vector<std::string> args={"progress",op};
    if(op=="inspect"||op=="restore")args.push_back(version);
    if(op=="restore"){args.push_back(saveSystem);args.push_back(saveStates?"states":"battery");}
    if(op=="target"||op=="auto")args.push_back(payload);
    task=start(args);
   }else if(page.find("music")==0){std::vector<std::string> args={"music",page=="music"?"status":page.substr(6)};if(!payload.empty())args.push_back(payload);task=start(args);}else task=start({page},payload);payload.clear();loading=true;}}
  if(loading&&task.wait_for(std::chrono::milliseconds(0))==std::future_status::ready){auto r=task.get();loading=false;populate(r);}
 }
 bool input(InputConfig* c,Input i) override{if(i.value&&c->isMappedTo("b",i)){if(loading&&(page=="saves-backup"||page=="saves-restore"||page=="saves-undo"))return true;back();return true;}if(loading||change)return true;if(i.value&&c->isMappedTo("x",i)){if(page.find("bluetooth")==0)request("bluetooth-scan");else if(page=="wifi-scan")request("wifi-scan");else if(page=="network")request("network");return true;}return menu->input(c,i);}
 HelpStyle getHelpStyle() override{return style();}
 std::vector<HelpPrompt> getHelpPrompts() override{return {{"a","select"},{"b","back"}};}
};
}
void openConsoleDeveloperPage(Window*w,const std::string& page){w->pushGui(new ConsoleSettings(w,false,page));}
void openConsoleControllerManager(Window*w){w->pushGui(new ConsoleControllers(w));}
void openConsoleControllerBluetooth(Window*w){w->pushGui(new ConsoleSettings(w,true));}
void openConsoleMusicPlayer(Window* w){w->pushGui(new ConsoleMusicPlayer(w));}
void openConsoleSystemSettings(Window* w){w->pushGui(new ConsoleSettings(w));}
bool consoleSystemSettingsTestState(Window* w,const char* expected){if(std::string(expected)=="CASTING"){auto c=dynamic_cast<ConsoleCasting*>(w->peekGui());return c&&c->ready();}if(std::string(expected).find("NETPLAY_")==0){auto n=dynamic_cast<ConsoleNetplay*>(w->peekGui());return n&&n->ready()&&std::string(expected)=="NETPLAY_"+n->current();}auto manager=dynamic_cast<ConsoleControllers*>(w->peekGui());if(std::string(expected).find("VIDEO_")==0){auto v=dynamic_cast<ConsoleMedia*>(w->peekGui());return v&&v->ready()&&(std::string(expected)=="VIDEO_posters"?v->hasPosters():std::string(expected)=="VIDEO_"+v->current());}if(std::string(expected)=="SOFTWARE_UPDATES"){auto u=dynamic_cast<ConsoleSoftwareUpdates*>(w->peekGui());return u&&u->ready();}std::string controllerExpected=expected;if(controllerExpected.find("CONTROLLERS_")==0)return manager&&manager->ready()&&controllerExpected=="CONTROLLERS_"+manager->current();if(controllerExpected=="MAIN_DEVELOPER")return dynamic_cast<GuiSettings*>(w->peekGui());if(controllerExpected=="CONTROLLER_TEST")return dynamic_cast<ConsoleControllerTest*>(w->peekGui());if(controllerExpected=="CONTROLLER_WIZARD")return dynamic_cast<ConsoleSafeControllerWizard*>(w->peekGui());if(controllerExpected=="CONTROLLER_TRIAL")return dynamic_cast<ConsoleControllerTrial*>(w->peekGui());if(controllerExpected=="CONTROLLER_RECOVERY")return dynamic_cast<ConsoleControllerRecovery*>(w->peekGui());auto s=dynamic_cast<ConsoleSettings*>(w->peekGui());std::string name=expected;if(name=="SONG_BANNER_VISIBLE")return songBanner&&songBanner->visible();if(name=="SONG_BANNER_HIDDEN"||name=="SONG_BANNER_FADED"||name=="SONG_BANNER_DISABLED")return !songBanner||!songBanner->visible();if(name=="SONG_BANNER_ART")return songBanner&&songBanner->visible()&&songBanner->hasArtwork();if(name=="SONG_TITLES_OFF")return Settings::getInstance()->getBool("MusicSongTitlesDisabled");if(name=="SONG_TITLES_ON")return !Settings::getInstance()->getBool("MusicSongTitlesDisabled");if(name.find("MUSIC_PLAYER")==0){auto p=dynamic_cast<ConsoleMusicPlayer*>(w->peekGui());if(!p||!p->ready())return false;if(name=="MUSIC_PLAYER_PAUSED")return p->value("PLAYBACK")=="Paused";if(name=="MUSIC_PLAYER_PLAYING")return p->value("PLAYBACK")=="Playing";if(name=="MUSIC_PLAYER_REPEAT_ONE")return p->value("REPEAT")=="one";return true;}if(name=="BROWSE_NOT_NES"){auto v=ViewController::get();return w->peekGui()==v&&v->getState().viewing==ViewController::GAME_LIST&&v->getState().getSystem()->getName()!="nes";}if(name=="HUD_ON"||name=="HUD_OFF")return Settings::getInstance()->getBool("ConsoleDeviceStats")==(name=="HUD_ON");if(name=="SYSTEM_POWER")return dynamic_cast<GuiSettings*>(w->peekGui());if(name=="SYSTEM_KEYBOARD")return dynamic_cast<ConsoleSettingsKeyboard*>(w->peekGui());if(name=="MUSIC_DETAILS")return dynamic_cast<GuiMsgBox*>(w->peekGui());if(name=="MUSIC_VOLUME_FOCUSED")return s&&s->ready()&&s->volumeFocused();if(name=="MUSIC_VOLUME_45")return s&&s->ready()&&s->musicVolume()==45;if(name=="MUSIC_SPOTIFY"||name=="MUSIC_LOCAL")return s&&s->ready()&&s->source()==(name=="MUSIC_SPOTIFY"?"spotify":"local");return s&&s->ready()&&name=="SYSTEM_"+s->current();}

void updateConsoleSongBanner(Window* w,int dt){
 static unsigned long frames=0;static int heartbeat=0;frames++;heartbeat+=dt;if(heartbeat>=5000){heartbeat=0;const char* temporary="/run/snes-updater-ui/frontend-ready.tmp";std::ofstream f(temporary);if(f){f<<"{\"pid\":"<<getpid()<<",\"frames\":"<<frames<<",\"width\":"<<Renderer::getScreenWidth()<<",\"height\":"<<Renderer::getScreenHeight()<<"}\n";f.close();std::rename(temporary,"/run/snes-updater-ui/frontend-ready.json");}}
consoleCastingTick(w,dt);controllerRecoveryTick(w,dt);if(!songBanner)songBanner.reset(new ConsoleSongBanner(w));songBanner->update(dt);}
void renderConsoleSongBanner(Window* w){if(songBanner&&!w->isSleeping()&&!dynamic_cast<ConsoleMusicPlayer*>(w->peekGui()))songBanner->render(Transform4x4f::Identity());}
void resetConsoleSongBanner(){songBanner.reset();}

void openConsoleNetplay(Window*w,FileData*g){w->pushGui(new ConsoleNetplay(w,g));}

int runConsoleMediaOnly(){
 consoleMediaStandalone=true;setenv("SNES_MEDIA_ONLY","1",1);
 int fd=-1;const char* inherited=getenv("SNES_MEDIA_LOCK_FD");
 if(inherited){int n=atoi(inherited);struct stat a,b;if(n>2&&fstat(n,&a)==0&&stat("/run/snes-updater/game.lock",&b)==0&&a.st_dev==b.st_dev&&a.st_ino==b.st_ino)fd=dup(n);}
 if(fd<0)fd=open("/run/snes-updater/game.lock",O_RDONLY|O_CLOEXEC);
 if(fd>=0&&flock(fd,LOCK_EX|LOCK_NB)!=0){close(fd);return 1;}
 Settings::getInstance()->setBool("ConsoleDeviceStats",false);Settings::getInstance()->setInt("ScreenSaverTime",0);Settings::getInstance()->setInt("MaxVRAM",32);
 Window window;if(!window.init()){if(fd>=0)close(fd);return 1;}window.pushGui(new ConsoleMedia(&window));
 LOG(LogInfo)<<"LookMovie media-only mode: no game library loaded";int last=SDL_GetTicks();bool running=true;
 while(running&&window.peekGui()){
  SDL_Event event;while(SDL_PollEvent(&event)){if(event.type==SDL_QUIT)running=false;else InputManager::getInstance()->parseEvent(event,&window);}
  if(!running||!window.peekGui())break;int now=SDL_GetTicks(),dt=std::max(0,now-last);last=now;window.update(std::min(dt,100));consoleExperienceTestTick(&window,std::min(dt,100));if(!window.peekGui())break;window.render();Renderer::swapBuffers();SDL_Delay(1);Log::flush();
 }
 while(window.peekGui())delete window.peekGui();window.deinit();if(fd>=0)close(fd);return 0;
}
