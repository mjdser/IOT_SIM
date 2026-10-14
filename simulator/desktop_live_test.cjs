const fs=require('node:fs'),path=require('node:path'),{spawn}=require('node:child_process');
module.exports=async(win,root)=>{
 const js=c=>win.webContents.executeJavaScript(c),wait=ms=>new Promise(r=>setTimeout(r,ms));
 await js("window.benchTest.view('camera')");await wait(300);
 const child=spawn(process.env.IOT_PYTHON||'python',[path.join(root,'test_live.py')],{cwd:root,windowsHide:true});
 let ended=false,code=null;child.on('exit',c=>{ended=true;code=c});child.stderr.on('data',d=>console.error(d.toString()));
 const events=[],texts=new Set();let screenshot=false;
 for(let i=0;i<400&&!ended;i++){
  const s=await js('window.pipelineTest.snapshot()');
  if(s.build.testing){
   if(events.at(-1)!==s.build.progress)events.push(s.build.progress);
   const text=s.tree.widgets.find(w=>w.id==='lbl_input')?.text;
   if(text!==undefined)texts.add(text);
   if(text==='HELLO'&&!screenshot){
    const pic=await win.webContents.capturePage();fs.writeFileSync(path.join(root,'test-results/live-testing.png'),pic.toPNG());screenshot=true;
   }
  }
  await wait(100);
 }
 if(!ended){child.kill();throw Error('Live tests timed out')}
 if(code!==0||events.length<5||!texts.has('HELLO')||!texts.has('HELLO WORLD'))throw Error('Missing actual keyboard test states: '+JSON.stringify({code,events,texts:[...texts]}));
 await wait(700);await js("window.pipelineTest.action({action:'reset'})");
 const point=await js("window.pipelineTest.point('key_h')");
 win.webContents.sendInputEvent({type:'mouseDown',button:'left',clickCount:1,...point});
 win.webContents.sendInputEvent({type:'mouseUp',button:'left',clickCount:1,...point});await wait(600);
 const click=(await js('window.pipelineTest.snapshot()')).tree;
 await js("window.pipelineTest.action({action:'reset'})");await js("window.pipelineTest.action({action:'tap_id',id:'key_h'})");
 const tap=(await js('window.pipelineTest.snapshot()')).tree;
 if(JSON.stringify(click)!==JSON.stringify(tap)||tap.widgets.find(w=>w.id==='lbl_input').text!=='H')throw Error('Glass click differs from TAP_ID');
 fs.writeFileSync(path.join(root,'test-results/live-desktop.json'),JSON.stringify({passed:true,events,texts:[...texts],clickMatchesTapId:true},null,2));
};
