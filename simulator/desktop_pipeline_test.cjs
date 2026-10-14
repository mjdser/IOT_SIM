// Actual Electron mouse input against the currently accepted generated UI.
const fs=require('node:fs'),path=require('node:path');
module.exports=async function(win,root){
 const js=code=>win.webContents.executeJavaScript(code),wait=ms=>new Promise(r=>setTimeout(r,ms));
 await js("window.benchTest.view('camera')");await wait(300);
 await js("window.pipelineTest.action({action:'reset'})");
 let snapshot=await js('window.pipelineTest.snapshot()');
 const sw=snapshot.tree.widgets.find(w=>w.type==='switch');
 const slider=snapshot.tree.widgets.find(w=>w.type==='slider');
 if(!sw||!slider)throw Error('This desktop test expects the live switch-and-slider demo');
 const point=await js(`window.pipelineTest.point(${JSON.stringify(sw.id)})`);
 win.webContents.sendInputEvent({type:'mouseDown',button:'left',clickCount:1,...point});
 win.webContents.sendInputEvent({type:'mouseUp',button:'left',clickCount:1,...point});await wait(650);
 await js('window.pipelineTest.idle()');const coordinateTree=(await js('window.pipelineTest.snapshot()')).tree;
 await js("window.pipelineTest.action({action:'reset'})");
 await js(`window.pipelineTest.action({action:'tap_id',id:${JSON.stringify(sw.id)}})`);
 const idTree=(await js('window.pipelineTest.snapshot()')).tree;
 const start=await js(`window.pipelineTest.point(${JSON.stringify(slider.id)},.2)`);
 const end=await js(`window.pipelineTest.point(${JSON.stringify(slider.id)},.75)`);
 win.webContents.sendInputEvent({type:'mouseDown',button:'left',...start});await wait(150);
 win.webContents.sendInputEvent({type:'mouseMove',button:'left',...end});await wait(100);
 win.webContents.sendInputEvent({type:'mouseUp',button:'left',...end});await wait(350);
 await js('window.pipelineTest.idle()');snapshot=await js('window.pipelineTest.snapshot()');
 const value=snapshot.tree.widgets.find(w=>w.id===slider.id).value;
 const range=snapshot.ranges.find(r=>r.x===slider.x&&r.y===slider.y);
 const expected=Math.round(range.min+.75*(range.max-range.min));
 const checks={readyForBoard:snapshot.build.ready_for_board,sameTapAndTapId:JSON.stringify(coordinateTree)===JSON.stringify(idTree),
  switchTurnsOn:coordinateTree.widgets.find(w=>w.id===sw.id).checked,sliderMouseDrag:Math.abs(value-expected)<=1,
  sourceHashRecorded:/^[a-f0-9]{64}$/.test(snapshot.build.source_sha256),portrait:snapshot.tree.screen.join('x')==='240x320'};
 if(Object.values(checks).some(x=>!x))throw Error(JSON.stringify({checks,value,expected}));
 const report={passed:true,checks,sliderValue:value,source_sha256:snapshot.build.source_sha256,revision:snapshot.build.revision,tree:snapshot.tree};
 fs.writeFileSync(path.join(root,'test-results','pipeline-desktop.json'),JSON.stringify(report,null,2));
 for(const view of ['camera','inspect','whole-bench']){
  await js(`window.benchTest.view('${view}')`);await wait(300);
  const image=await win.webContents.capturePage(undefined,{stayAwake:true});
  if(image.isEmpty())throw Error('Empty screenshot');
  fs.writeFileSync(path.join(root,'test-results',`pipeline-${view}.png`),image.toPNG());
 }
 return report;
};
