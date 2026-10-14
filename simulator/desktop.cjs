const {app,BrowserWindow,ipcMain,dialog,shell}=require('electron');
const {spawn}=require('node:child_process');
const path=require('node:path');
const readline=require('node:readline');
let bridge,endpoint,win;
const smoke=['IOT_SMOKE','IOT_PIPELINE_SMOKE','IOT_GAME_SMOKE','IOT_THEME_SMOKE','IOT_LIVE_SMOKE'].some(name=>process.env[name]==='1');
if(!process.env.IOT_MIRROR)process.env.IOT_MIRROR=smoke?'0':'1';
app.whenReady().then(()=>{
  bridge=spawn(process.env.IOT_PYTHON || 'python',[path.join(__dirname,'bridge.py')],{cwd:__dirname,windowsHide:true});
  bridge.stderr.on('data',d=>console.error(d.toString()));
  bridge.on('error',e=>{dialog.showErrorBox('Cannot start LVGL',e.message);app.quit()});
  bridge.on('exit',code=>{if(win&&!win.isDestroyed())win.webContents.send('host-exit',code);else if(!win){dialog.showErrorBox('LVGL could not start','Build the host with python build.py. Check that Python 3 is installed.');app.quit()}});
  readline.createInterface({input:bridge.stdout}).once('line',line=>{
    endpoint=JSON.parse(line);
    win=new BrowserWindow({width:1440,height:940,minWidth:1000,minHeight:700,backgroundColor:'#151b20',title:'IOT · Bench simulator',autoHideMenuBar:true,
      webPreferences:{preload:path.join(__dirname,'preload.cjs'),contextIsolation:true,nodeIntegration:false,sandbox:true}});
    win.loadFile('index.html');
    win.webContents.setBackgroundThrottling(false);
    win.webContents.setWindowOpenHandler(()=>({action:'deny'}));
    win.webContents.on('will-navigate',event=>event.preventDefault());
    if(process.env.IOT_GAME_SMOKE==='1'){
      win.webContents.once('did-finish-load',()=>setTimeout(async()=>{
        try{await require('./desktop_game_test.cjs')(win,__dirname);app.quit()}
        catch(e){console.error(e);app.exit(1)}
      },1500));
    }
    if(process.env.IOT_THEME_SMOKE==='1'){
      win.webContents.once('did-finish-load',()=>setTimeout(async()=>{
        try{await require('./desktop_theme_test.cjs')(win,__dirname);app.quit()}
        catch(e){console.error(e);app.exit(1)}
      },1500));
    }
    if(process.env.IOT_LIVE_SMOKE==='1'){
      win.webContents.once('did-finish-load',()=>setTimeout(async()=>{
        try{await require('./desktop_live_test.cjs')(win,__dirname);app.quit()}
        catch(e){console.error(e);app.exit(1)}
      },1500));
    }
    if(process.env.IOT_PIPELINE_SMOKE==='1'){
      win.webContents.once('did-finish-load',()=>setTimeout(async()=>{
        try{await require('./desktop_pipeline_test.cjs')(win,__dirname);app.quit()}
        catch(error){require('node:fs').writeFileSync(path.join(__dirname,'test-results','pipeline-desktop-error.txt'),String(error.stack));app.exit(1)}
      },1800));
    }
    if(process.env.IOT_SMOKE==='1'){
      win.webContents.once('did-finish-load',()=>setTimeout(async()=>{
        try {
          const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
          const js=code=>win.webContents.executeJavaScript(code);
          await js("window.benchTest.view('camera')");await wait(200);
          const point=await js("window.benchTest.keyPoint('key_a')");
          win.webContents.sendInputEvent({type:'mouseDown',button:'left',clickCount:1,...point});
          win.webContents.sendInputEvent({type:'mouseUp',button:'left',clickCount:1,...point});await wait(700);
          const pointerClick=await js("document.getElementById('note').textContent==='A'");
          await js("window.benchTest.view('whole-bench')");await wait(300);
          let before=await js('window.benchTest.pose()');
          const drag=async button=>{win.webContents.sendInputEvent({type:'mouseDown',button,x:800,y:420});win.webContents.sendInputEvent({type:'mouseMove',button,x:880,y:450});win.webContents.sendInputEvent({type:'mouseUp',button,x:880,y:450});await wait(400)};
          await drag('left');let after=await js('window.benchTest.pose()');const orbitDrag=JSON.stringify(before.position)!==JSON.stringify(after.position);
          before=after;await drag('right');after=await js('window.benchTest.pose()');const panDrag=JSON.stringify(before.target)!==JSON.stringify(after.target);
          before=after;win.webContents.sendInputEvent({type:'mouseWheel',x:800,y:420,deltaY:120,deltaX:0});await wait(400);after=await js('window.benchTest.pose()');const scrollDolly=Math.abs(before.distance-after.distance)>.001;
          const report=await js('window.benchTest.run()');Object.assign(report,{pointerClick,orbitDrag,panDrag,scrollDolly});
          if(Object.values(report).some(x=>!x))throw Error(JSON.stringify(report));
          require('node:fs').writeFileSync(path.join(__dirname,'test-results','desktop.json'),JSON.stringify(report,null,2));
          const pic=await win.webContents.capturePage(undefined,{stayAwake:true});if(pic.isEmpty())throw Error('Empty desktop screenshot');require('node:fs').writeFileSync(path.join(__dirname,'test-results','desktop.png'),pic.toPNG());
          for(const view of ['whole-bench','camera']){
            await win.webContents.executeJavaScript(`window.benchTest.view('${view}')`);
            await new Promise(resolve=>setTimeout(resolve,300));
            const shot=await win.webContents.capturePage(undefined,{stayAwake:true});if(shot.isEmpty())throw Error('Empty '+view+' screenshot');require('node:fs').writeFileSync(path.join(__dirname,'test-results',view+'.png'),shot.toPNG());
          }
          app.quit();
        } catch(e){console.error(e);app.exit(1)}
      },1500));
    }
  });
});
ipcMain.handle('bench-command',async(_,data)=>{
  const response=await fetch(`http://127.0.0.1:${endpoint.port}`,{method:'POST',headers:{'Content-Type':'application/json','X-Bench-Token':endpoint.token},body:JSON.stringify(data)});
  const result=await response.json();if(!response.ok)throw Error(result.error);return result;
});
ipcMain.handle('open-chat',()=>shell.openExternal('http://127.0.0.1:8765'));
app.on('window-all-closed',()=>app.quit());
app.on('before-quit',()=>{if(bridge)bridge.kill()});
