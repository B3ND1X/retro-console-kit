// Paged, lazy-poster media UI shared by the standalone port and native test tools.
static bool consoleMediaStandalone=false;
class ConsoleMedia:public GuiComponent {
 struct Episode{int season,number;std::string title,url;};std::vector<Episode> episodes;int selectedSeason=1;std::string mediaKind="movies";
 struct Movie{std::string title,year,rating,url,poster;};
 std::unique_ptr<MenuComponent> menu;std::vector<std::shared_ptr<GuiComponent>> pieces;std::vector<std::shared_ptr<ImageComponent>> images;std::map<std::string,std::string> cached;
 std::future<Result> task,imageTask;bool waiting=false,imageWaiting=false,more=false;std::string page="root",catalogKind="browse",operation,genre,query,title,session,infoText;int serverPage=1,selected=0,offset=0;unsigned imageGeneration=0,wantedGeneration=0;std::vector<Movie> movies;std::vector<std::string> qualities;std::shared_ptr<TextComponent> caption;
 void clear(){if(menu){removeChild(menu.get());menu.reset();}for(auto p:pieces)removeChild(p.get());pieces.clear();images.clear();caption.reset();}
 void row(const std::string& label,const std::string& value="",std::function<void()> callback=nullptr){ComponentListRow r;auto a=std::make_shared<TextComponent>(mWindow,label,Font::get(FONT_SIZE_SMALL),0x555555FF);a->setSize(Renderer::getScreenHeight()*.68f,0);r.addElement(a,true);if(!value.empty()){auto b=std::make_shared<TextComponent>(mWindow,value,Font::get(FONT_SIZE_SMALL),0x3377AAFF);r.addElement(b,false);}if(callback)r.makeAcceptInputHandler(callback);menu->addRow(r);}
 void reset(const std::string& label){clear();menu.reset(new MenuComponent(mWindow,label.c_str()));addChild(menu.get());}
 void finish(){menu->addButton("BACK","return",[this]{back();});setSize(menu->getSize());setPosition((Renderer::getScreenWidth()-mSize.x())/2,(Renderer::getScreenHeight()-mSize.y())/2);LOG(LogInfo)<<"Console video player ready: "<<page;}
 void message(const std::string& s){mWindow->pushGui(new GuiMsgBox(mWindow,s,"OK",nullptr));}
 void keyboard(){mWindow->pushGui(new ConsoleSettingsKeyboard(mWindow,"SEARCH MOVIES & TV","",false,[this](const std::string& value){query=value;request("search","{\"query\":"+json(value)+"}");}));}
 void root(){page="root";reset("LOOKMOVIE");row("BROWSE MOVIES","",[this]{mediaKind="movies";genre.clear();serverPage=1;browse();});row("BROWSE TV SHOWS","",[this]{mediaKind="shows";genre.clear();serverPage=1;browse();});row("GENRES","",[this]{genres();});row("SEARCH MOVIES & TV","",[this]{keyboard();});row("PLAYBACK CONTROLS","VIEW",[this]{message("A: play / pause\nB: stop and return\nLeft / Right: seek\nUp / Down: movie volume\nY: return to quality selection\n\nBrowser: X search, Y genres, shoulders change catalogue page. Movies and TV episodes; available quality is provided by the website.");});finish();}
 void genres(){request("genres","{\"kind\":"+json(mediaKind)+"}");}
 void browse(){request("browse","{\"kind\":"+json(mediaKind)+",\"genre\":"+json(genre)+",\"page\":"+std::to_string(serverPage)+"}");}
 void textAt(const std::string& value,float x,float y,float width,float height,float font,unsigned color=0xEEEEEEFF){auto t=std::make_shared<TextComponent>(mWindow,value,Font::get(font),color);t->setPosition(x,y);t->setSize(width,height);addChild(t.get());pieces.push_back(t);}
 void posters(){if(imageWaiting||page!="grid")return;std::string data="{\"urls\":[";bool first=true;for(int i=offset;i<std::min(offset+8,int(movies.size()));i++)if(!movies[i].poster.empty()&&!cached.count(movies[i].poster)){if(!first)data+=",";data+=json(movies[i].poster);first=false;}data+="]}";if(first)return;imageTask=start({"media","posters"},data);imageWaiting=true;wantedGeneration=imageGeneration;}
 void grid(){
  page="grid";clear();setPosition(0,0);setSize(Renderer::getScreenWidth(),Renderer::getScreenHeight());offset=selected/8*8;imageGeneration++;
  const float w=mSize.x(),h=mSize.y();textAt("LOOKMOVIE",.055f*w,.025f*h,.75f*w,.065f*h,.045f*h);
  std::string context=catalogKind=="search"?"Search: "+query:(genre.empty()?(mediaKind=="shows"?"Browse TV shows":"Browse movies"):genre);context+="  |  Page "+std::to_string(serverPage)+"  |  "+std::to_string(offset+1)+"-"+std::to_string(std::min(offset+8,int(movies.size())))+" / "+std::to_string(movies.size());textAt(context,.055f*w,.095f*h,.9f*w,.045f*h,.025f*h,0xA9C7DDFF);
  for(int i=offset;i<std::min(offset+8,int(movies.size()));i++){
   int cell=i-offset;float x=(.06f+(cell%4)*.225f)*w,y=(.16f+(cell/4)*.385f)*h;
   auto image=std::make_shared<ImageComponent>(mWindow,false,false);image->setMaxSize(.19f*w,.285f*h);image->setOrigin(.5f,0);image->setPosition(x+.10f*w,y+.015f*h);
   auto found=cached.find(movies[i].poster);if(found!=cached.end())image->setImage(found->second);addChild(image.get());pieces.push_back(image);images.push_back(image);
   std::string name=(movies[i].url.find("/shows/")!=std::string::npos?"TV | ":"FILM | ")+movies[i].title;if(name.size()>43)name=name.substr(0,40)+"...";textAt(name,x+.012f*w,y+.30f*h,.185f*w,.043f*h,.023f*h);textAt(movies[i].year+(movies[i].rating.empty()?"":"  |  Rating "+movies[i].rating),x+.012f*w,y+.34f*h,.185f*w,.03f*h,.019f*h,0xB9C8D4FF);
  }
  posters();updateHelpPrompts();LOG(LogInfo)<<"Console video player ready: grid movies="<<movies.size()<<" page="<<serverPage;
 }
 void choose(){if(movies.empty())return;title=movies[selected].title;request("info","{\"url\":"+json(movies[selected].url)+"}");}
 bool isShow()const{return !movies.empty()&&movies[selected].url.find("/shows/")!=std::string::npos;}
 void seasons(){page="seasons";reset("CHOOSE SEASON");int last=-1;for(auto e:episodes)if(e.season!=last){last=e.season;row("SEASON "+std::to_string(last),"",[this,e]{selectedSeason=e.season;episodeList();});}finish();}
 void episodeList(){page="episodes";reset(("SEASON "+std::to_string(selectedSeason)+" - EPISODES"));for(auto e:episodes)if(e.season==selectedSeason)row("E"+std::to_string(e.number)+" - "+e.title,"",[this,e]{request("resolve","{\"url\":"+json(e.url)+"}");});finish();}
 void details(){page="info";reset(isShow()?"TV SHOW INFORMATION":"MOVIE INFORMATION");row(movies[selected].title);row(movies[selected].year,movies[selected].rating);row(isShow()?"SEASONS & EPISODES":"WATCH","",[this]{request(isShow()?"episodes":"resolve","{\"url\":"+json(movies[selected].url)+"}");});row("SYNOPSIS","VIEW",[this]{message(infoText);});finish();}
 void quality(){page="quality";reset("CHOOSE QUALITY");row(title);for(auto q:qualities)row("PLAY",q,[this,q]{request("prepare","{\"quality\":"+json(q)+",\"session\":"+json(session)+"}");});finish();}
 void request(const std::string& op,const std::string& data="{}"){if(waiting)return;operation=op;task=start({"media",op},data);waiting=true;reset(op=="search"?"SEARCHING MOVIES":"LOOKMOVIE");row(op=="resolve"?"GETTING AVAILABLE STREAMS...":"PLEASE WAIT...");finish();}
 void play(){
  int fd=-1;if(!consoleMediaStandalone){fd=open("/run/snes-updater/game.lock",O_RDONLY|O_CLOEXEC);if(fd>=0&&flock(fd,LOCK_EX|LOCK_NB)!=0){close(fd);message("Wait for the software update to finish before watching.");quality();return;}}
  AudioManager::getInstance()->deinit();VolumeControl::getInstance()->deinit();mWindow->deinit();runSystemCommand("/usr/bin/python3 /usr/local/lib/snes-console/media.py play");mWindow->init();VolumeControl::getInstance()->init();mWindow->normalizeNextUpdate();if(fd>=0)close(fd);request("status");
 }
 void back(){if(waiting){delete this;return;}if(page=="root"){delete this;return;}if(page=="info")grid();else if(page=="quality"){if(isShow())episodeList();else details();}else if(page=="episodes")seasons();else if(page=="seasons")details();else root();}
public:
 ConsoleMedia(Window*w):GuiComponent(w){root();}
 bool ready()const{return !waiting;}
 std::string current()const{return page;}
 bool hasPosters()const{for(auto image:images)if(image->getTextureSize().x()>0)return true;return false;}
 void update(int dt)override{GuiComponent::update(dt);
  if(imageWaiting&&imageTask.wait_for(std::chrono::milliseconds(0))==std::future_status::ready){auto r=imageTask.get();imageWaiting=false;if(r.first){for(auto v:rows(r.second))if(v.size()>=3&&v[0]=="POSTER")cached[v[1]]=v[2];if(cached.size()>100)cached.clear();if(page=="grid")for(size_t i=0;i<images.size();i++){auto f=cached.find(movies[offset+i].poster);if(f!=cached.end())images[i]->setImage(f->second);}}posters();}
  if(!waiting||task.wait_for(std::chrono::milliseconds(0))!=std::future_status::ready)return;auto r=task.get();waiting=false;if(!r.first){if(movies.empty())root();else grid();message(r.second);return;}auto list=rows(r.second);
  if(operation=="browse"||operation=="search"){
   catalogKind=operation;movies.clear();cached.clear();selected=0;more=false;if(operation=="search")serverPage=1;
   for(auto v:list){if(v.size()>=3&&v[0]=="CATALOG")more=v[2]=="YES";if(v.size()>=6&&v[0]=="MOVIE")movies.push_back({v[1],v[2],v[3],v[4],v[5]});if(v.size()>=7&&v[0]=="RESULT")movies.push_back({v[2],v[3],v[5],v[4],v[6]});}
   if(movies.empty()){root();message("No movies were found.");}else grid();
  }else if(operation=="genres"){page="genres";reset(mediaKind=="shows"?"TV GENRES":"MOVIE GENRES");for(auto v:list)if(v.size()>=3&&v[0]=="GENRE")row(v[2],"",[this,v]{genre=v[1];serverPage=1;browse();});finish();}
  else if(operation=="info"){infoText="Movie information unavailable.";for(auto v:list)if(v.size()>=2&&v[0]=="INFO")infoText=v[1];details();}
  else if(operation=="episodes"){episodes.clear();for(auto v:list)if(v.size()>=5&&v[0]=="EPISODE")episodes.push_back({atoi(v[1].c_str()),atoi(v[2].c_str()),v[3],v[4]});if(episodes.empty()){details();message("No episodes were available.");}else seasons();}
  else if(operation=="resolve"){qualities.clear();for(auto v:list)if(v.size()>=2){if(v[0]=="TITLE")title=v[1];if(v[0]=="SESSION")session=v[1];if(v[0]=="QUALITY")qualities.push_back(v[1]);}quality();}
  else if(operation=="prepare")play();else if(operation=="status"){quality();for(auto v:list)if(v.size()>=2&&v[0]=="ERROR"&&!v[1].empty())message(v[1]);}
 }
 bool input(InputConfig*c,Input i)override{
  if(i.value&&c->isMappedTo("b",i)){back();return true;}if(waiting)return true;
  if(page=="grid"){
   if(!i.value)return true;
   if(c->isMappedTo("a",i))choose();else if(c->isMappedTo("x",i))keyboard();else if(c->isMappedTo("y",i))genres();else if(c->isMappedTo("start",i))root();
   else if(c->isMappedTo("rightshoulder",i)&&catalogKind!="search"&&more){serverPage++;browse();}
   else if(c->isMappedTo("leftshoulder",i)&&catalogKind!="search"&&serverPage>1){serverPage--;browse();}
   else {int d=c->isMappedLike("left",i)?-1:c->isMappedLike("right",i)?1:c->isMappedLike("up",i)?-4:c->isMappedLike("down",i)?4:0;int old=offset;selected=std::max(0,std::min(int(movies.size())-1,selected+d));if(selected/8*8!=old)grid();}return true;
  }return menu->input(c,i);
 }
 void render(const Transform4x4f& t)override{
  if(page=="grid"){Renderer::setMatrix(Transform4x4f::Identity());Renderer::drawRect(0,0,mSize.x(),mSize.y(),0x101821FF,0x101821FF);for(int j=0;j<int(images.size());j++){float x=(.06f+(j%4)*.225f)*mSize.x(),y=(.16f+(j/4)*.385f)*mSize.y();unsigned color=offset+j==selected?0x245A7EFF:0x192734FF;Renderer::drawRect(x,y,.20f*mSize.x(),.375f*mSize.y(),color,color);if(!images[j]->hasImage()){Renderer::drawRect(x+.055f*mSize.x(),y+.06f*mSize.y(),.09f*mSize.x(),.20f*mSize.y(),0x334B5FFF,0x334B5FFF);}}}GuiComponent::render(t);
 }
 HelpStyle getHelpStyle()override{return style();}
 std::vector<HelpPrompt> getHelpPrompts()override{return page=="grid"?std::vector<HelpPrompt>{{"a","title info"},{"b","back"},{"x","search"},{"y","genres"},{"lr","page"}}:std::vector<HelpPrompt>{{"a","select"},{"b","back"}};}
};
