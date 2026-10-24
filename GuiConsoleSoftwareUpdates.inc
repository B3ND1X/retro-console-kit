// Controller-operated OTA management; network/install work runs in a one-shot service.
class ConsoleSoftwareUpdates:public GuiComponent {
 std::unique_ptr<MenuComponent> menu;std::future<Result> task;bool waiting=false,history=false;int elapsed=0;std::map<std::string,std::string> values;std::string last,notes;
 void request(const std::string& action="status",const std::string& data=""){if(waiting)return;task=start({"software-update",action},data);waiting=true;elapsed=0;}
 void row(const std::string& text,const std::string& value="",std::function<void()> cb=nullptr){ComponentListRow r;auto a=std::make_shared<TextComponent>(mWindow,text,Font::get(FONT_SIZE_SMALL),0x555555FF);r.addElement(a,true);if(!value.empty()){auto b=std::make_shared<TextComponent>(mWindow,value,Font::get(FONT_SIZE_SMALL),0x3377AAFF);r.addElement(b,false);}if(cb)r.makeAcceptInputHandler(cb);menu->addRow(r);}
 void message(const std::string& text){mWindow->pushGui(new GuiMsgBox(mWindow,text,"OK",nullptr));}
 void confirm(const std::string& action,const std::string& text){mWindow->pushGui(new GuiMsgBox(mWindow,text,"CANCEL",nullptr,"CONTINUE",[this,action]{request(action);}));}
 bool busy()const{auto p=values.find("PHASE");if(p==values.end())return false;return p->second=="QUEUED"||p->second=="CHECKING"||p->second=="DOWNLOADING"||p->second=="VERIFYING"||p->second=="INSTALLING"||p->second=="VALIDATING"||p->second=="ROLLING_BACK";}
 void drawMenu(){
  if(menu)removeChild(menu.get());menu.reset(new MenuComponent(mWindow,"SOFTWARE UPDATES"));addChild(menu.get());
  row("INSTALLED VERSION",values["INSTALLED"]);row("LATEST VERSION",values["LATEST"].empty()?"Not checked":values["LATEST"]);
  row("STATUS",values["PHASE"]);row("DETAILS","VIEW",[this]{message(values["MESSAGE"]+"\n\n"+values["TRUST"]);});
  if(busy())row("PROGRESS",values["PROGRESS"]+"%");
  if(!busy()){
   row("CHECK FOR UPDATES","",[this]{request("check");});
   if(!values["LATEST"].empty()){
    long bytes=std::strtol(values["SIZE"].c_str(),nullptr,10);row("DOWNLOAD SIZE",std::to_string(bytes/1024)+" KiB");
    row("RELEASE NOTES","VIEW",[this]{message(notes.empty()?"No release notes":notes);});
    row("INSTALL UPDATE","",[this]{confirm("install","Install version "+values["LATEST"]+"?\nYour games, saves and personal settings are preserved. The frontend will restart after verification.");});
   }
   row("AUTOMATIC CHECKS",values["AUTO"],[this]{request("automatic",std::string("{\"enabled\":")+(values["AUTO"]=="On"?"false":"true")+"}");});
   row("UPDATE HISTORY","VIEW",[this]{history=true;request("history");});
   if(values["PREVIOUS"]=="Yes")row("RESTORE PREVIOUS VERSION","",[this]{confirm("rollback","Restore the previous application version? Games and personal settings are preserved.");});
   row("RESTART FRONTEND","",[this]{confirm("restart","Restart EmulationStation now?");});
   row("GITHUB REPOSITORY","EDIT",[this]{mWindow->pushGui(new ConsoleSettingsKeyboard(mWindow,"GITHUB OWNER/REPOSITORY","",false,[this](const std::string& s){request("repository","{\"repository\":"+json(s)+"}");}));});
  }
  menu->addButton("BACK","return",[this]{delete this;});setSize(menu->getSize());setPosition((Renderer::getScreenWidth()-mSize.x())/2,(Renderer::getScreenHeight()-mSize.y())/2);
 }
public:
 ConsoleSoftwareUpdates(Window*w):GuiComponent(w){drawMenu();request();}
 bool ready()const{return values.count("INSTALLED")>0;}
 void update(int dt)override{
  GuiComponent::update(dt);elapsed+=dt;
  if(waiting&&task.wait_for(std::chrono::milliseconds(0))==std::future_status::ready){auto r=task.get();waiting=false;
   if(!r.first){message(r.second);elapsed=-3000;}
   else {std::string historyText;notes.clear();for(auto v:rows(r.second)){if(v.size()<2)continue;if(v[0]=="NOTE")notes+=v[1]+"\n";else if(v[0]=="HISTORY")historyText+=v[1]+"\n";else values[v[0]]=v[1];}
    if(history){history=false;message(historyText.empty()?"No updates have been installed":historyText);}
    if(r.second!=last){last=r.second;drawMenu();}
   }
  }
  if(!waiting&&elapsed>2000&&mWindow->peekGui()==this)request();
 }
 bool input(InputConfig*c,Input i)override{if(i.value&&c->isMappedTo("b",i)){delete this;return true;}return menu->input(c,i);}
 HelpStyle getHelpStyle()override{return style();}
 std::vector<HelpPrompt> getHelpPrompts()override{return {{"a","select"},{"b","back"}};}
};
