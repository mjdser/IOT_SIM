import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
const $=id=>document.getElementById(id), viewport=$('viewport'), area=$('renderArea');
const scene=new THREE.Scene();scene.background=new THREE.Color('#d7dedd');
const renderer=new THREE.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));
renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;
area.append(renderer.domElement);renderer.domElement.tabIndex=0;
const eye=new THREE.PerspectiveCamera(42,1,.001,20);
const orbit=new OrbitControls(eye,renderer.domElement);orbit.enableDamping=true;orbit.dampingFactor=.12;
orbit.minDistance=.045;orbit.maxDistance=3;orbit.maxPolarAngle=Math.PI*.49;orbit.target.set(.02,.88,-.03);
eye.position.set(.86,1.40,1.15);orbit.update();
scene.add(new THREE.HemisphereLight(0xf7fcff,0x727b70,2.4));
const sun=new THREE.DirectionalLight(0xfff7e8,3.0);sun.position.set(-.6,2.5,1);sun.castShadow=true;
sun.shadow.mapSize.set(2048,2048);sun.shadow.camera.left=-1;sun.shadow.camera.right=1;sun.shadow.camera.top=1;sun.shadow.camera.bottom=-1;sun.shadow.normalBias=.001;scene.add(sun);
const mats={};
function mat(color,metalness=0,roughness=.65){const key=[color,metalness,roughness].join();return mats[key]??=new THREE.MeshStandardMaterial({color,metalness,roughness})}
function box(w,h,d,x,y,z,color,metal=0){const o=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),mat(color,metal));o.position.set(x,y,z);o.castShadow=true;o.receiveShadow=true;scene.add(o);return o}
function tube(a,b,r,color,metal=0){const p=new THREE.Vector3(...a),q=new THREE.Vector3(...b);const o=new THREE.Mesh(new THREE.CylinderGeometry(r,r,p.distanceTo(q),24),mat(color,metal,.34));o.position.copy(p).add(q).multiplyScalar(.5);o.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),q.sub(p).normalize());o.castShadow=true;o.receiveShadow=true;scene.add(o);return o}
function cable(points,color,r=.0012){const curve=new THREE.CatmullRomCurve3(points.map(p=>new THREE.Vector3(...p)));const o=new THREE.Mesh(new THREE.TubeGeometry(curve,48,r,7,false),mat(color,0,.48));o.castShadow=true;scene.add(o);return o}
function tag(text,x,y,z,width=.10){const c=document.createElement('canvas');c.width=512;c.height=96;const ctx=c.getContext('2d');ctx.fillStyle='#deebe7';ctx.fillRect(0,0,512,96);ctx.fillStyle='#304f56';ctx.font='600 32px Segoe UI';ctx.textAlign='center';ctx.fillText(text,256,60);const t=new THREE.CanvasTexture(c);t.colorSpace=THREE.SRGBColorSpace;const o=new THREE.Mesh(new THREE.PlaneGeometry(width,width*96/512),new THREE.MeshBasicMaterial({map:t,side:THREE.DoubleSide}));o.rotation.x=-Math.PI/2;o.position.set(x,y,z);scene.add(o);return o}
// Metres. Only active-glass dimensions are specified measurements. All other
// dimensions are photo estimates, not a mechanical CAD or pin-location model.
box(1.2,.035,.76,0,.72,0,0xedece4); // white tabletop
for(const x of [-.51,.51])for(const z of [-.29,.29])box(.035,.69,.035,x,.357,z,0x8d979a,.65);
box(8,.01,8,0,.002,0,0xc3cbc8);
const sx=-.24,sz=-.115;
box(.19,.009,.16,sx,.744,sz,0xa66d43); // box base & orange lining
box(.184,.004,.154,sx,.751,sz,0xcc693e);
box(.19,.065,.005,sx,.776,sz-.08,0x333334);box(.19,.065,.005,sx,.776,sz+.08,0x333334);
box(.005,.065,.16,sx-.095,.776,sz,0x3b3938);box(.005,.065,.16,sx+.095,.776,sz,0x3b3938);
box(.064,.02,.059,sx,.769,sz,0x7f888c);tube([sx,.77,sz],[sx,1.39,sz],.012,0xaab4b7,.75);
tube([-.53,1.13,sz],[.223,1.13,sz],.011,0xb4bec0,.75);
box(.045,.059,.045,sx,1.13,sz,0x7b838a);box(.057,.028,.04,sx,1.138,sz,0x8f989d);
tube([sx,1.13,sz+.022],[sx,1.13,sz+.029],.007,0x555f65,.5);
// One webcam: grey clamp, underside PCB and one downward lens.
const gx=.19,gz=sz,glassY=.7508,lensPos=new THREE.Vector3(gx,1.089,gz);
const webcam=new THREE.Group();scene.add(webcam);
for(const o of [box(.038,.047,.04,gx,1.13,gz,0x90999e),box(.059,.013,.046,gx,1.101,gz,0x8e979e),box(.040,.002,.03,gx,1.093,gz,0x20372f),tube([gx,1.092,gz],[gx,1.084,gz],.0056,0x131d23),tube([gx,1.084,gz],[gx,1.083,gz],.0035,0x20303b,.4),tube([gx,1.133,gz+.021],[gx,1.133,gz+.026],.006,0x657077,.5)])webcam.attach(o);
cable([[gx,1.117,gz+.019],[.12,1.128,gz+.023],[-.10,1.185,gz+.018],[sx,1.161,gz+.025],[sx-.025,1.08,gz+.025],[sx+.017,.85,gz+.06],[-.13,.751,.09],[-.41,.745,.25],[-.61,.69,.27],[-.63,.39,.27]],0x171b20,.0031);
// Red module, metal bezel, and exact 43.2 x 57.6 mm active glass.
box(.052,.0016,.081,gx,.7408,gz+.005,0xa3252e);
box(.047,.006,.064,gx,.7445,gz,0xaab2b4,.65);
box(.045,.0014,.0595,gx,.7483,gz,0x161d22);
const frameBytes=new Uint8Array(240*320*4);frameBytes.fill(255);
const tex=new THREE.DataTexture(frameBytes,240,320,THREE.RGBAFormat);
tex.minFilter=THREE.NearestFilter;tex.magFilter=THREE.NearestFilter;tex.generateMipmaps=false;tex.colorSpace=THREE.SRGBColorSpace;
const glass=new THREE.Mesh(new THREE.PlaneGeometry(.0432,.0576),new THREE.MeshBasicMaterial({map:tex,toneMapped:false}));
glass.rotation.x=-Math.PI/2;glass.position.set(gx,glassY,gz);scene.add(glass);
for(const x of [gx-.022,gx+.022])for(const z of [gz-.031,gz+.04]){
 tube([x,.7418,z],[x,.7425,z],.0018,0xc8b389,.65);tube([x,.7426,z],[x,.7428,z],.0009,0x343133);
}
// Black DevKit with CP2102, RF can, USB connector and male header strips.
const ex=.103,ez=gz;
box(.029,.0016,.054,ex,.741,ez,0x172b2a);box(.018,.003,.022,ex,.744,ez-.010,0xb8bec0,.6);
box(.012,.002,.007,ex,.7437,ez+.009,0x202528);box(.008,.004,.006,ex,.744,ez+.026,0xb8c0c2,.65);
tag('ESP32',ex,.746,ez-.011,.015);
for(const x of [ex-.012,ex+.012])for(let i=0;i<15;i++){
 box(.0025,.002,.0025,x,.743,ez-.022+i*.0031,0x1b2025);
 box(.00065,.004,.00065,x,.746,ez-.022+i*.0031,0xc2ac72,.55);
}
for(let i=0;i<14;i++){
 const x=gx-.019+i*.0029;
 box(.0025,.0025,.0025,x,.743,gz+.039,0x161c21);box(.0006,.004,.0006,x,.746,gz+.039,0xc2ac72,.5);
}
const wiring=[['19','TFT_MISO','#9c79bf'],['23','TFT_MOSI','#d68043'],['18','TFT_SCLK','#d6b54d'],['5','TFT_CS','#638fcc'],['15','TFT_DC','#b9757f'],['4','TFT_RST','#71a585'],['21','TOUCH_CS','#b0b8bd'],['3V3','VCC','#bd4f4f'],['GND','GND','#272b33'],['3V3','LED','#b74b40']];
for(let i=0;i<wiring.length;i++){
 const ax=ex+.012,az=ez-.020+i*.0043,bx=gx-.018+i*.0038,bz=gz+.039;
 box(.0025,.006,.0025,ax,.748,az,0x242a30);box(.0025,.006,.0025,bx,.748,bz,0x242a30);
 cable([[ax,.751,az],[ax+.007,.766+i*.001,az+.017],[(ax+bx)/2,.755+i*.001,bz+.03],[bx,.767,bz+.014],[bx,.751,bz]],wiring[i][2],.00067);
}
tag('ESP32  /  ILI9341',.156,.739,.006,.125);
// Electrical net labels are authoritative; 3D routing/header slot positions are illustrative.
$('pins').innerHTML=wiring.map(([pin,signal])=>`<dt>${signal}</dt><dd>${pin==='3V3'?'3.3 V':pin==='GND'?'GND':'GPIO '+pin}</dd>`).join('');
let cameraMode=false,savedView,themeLight=false,tree,ranges=[],buildInfo={},serial=Promise.resolve(),running=true;
const keys=new Set();const ray=new THREE.Raycaster();const mouse=new THREE.Vector2();
function toast(message){$('toast').textContent=message;$('toast').style.display='block';clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('toast').style.display='none',6000)}
function drawFrame(data){
 const raw=atob(data.frame);if(raw.length!==153600)throw Error('Wrong framebuffer dimensions');
 // Raw rows are top-down; WebGL UVs are bottom-up. Reverse rows exactly once.
 for(let y=0;y<320;y++)for(let x=0;x<240;x++){
  const s=2*(y*240+x),v=raw.charCodeAt(s)|(raw.charCodeAt(s+1)<<8),d=4*((319-y)*240+x);
  const r=v>>11,g=(v>>5)&63,b=v&31;frameBytes[d]=(r<<3)|(r>>2);frameBytes[d+1]=(g<<2)|(g>>4);frameBytes[d+2]=(b<<3)|(b>>2);frameBytes[d+3]=255;
 }tex.needsUpdate=true;tree=data.tree;ranges=data.ranges||[];buildInfo=data.build||{};
 const primary=tree.widgets.find(w=>w.id==='lbl_note')||tree.widgets.find(w=>w.type==='label')||tree.widgets[0];
 $('widgetCount').textContent=tree.widgets.length;$('primaryId').textContent=primary?.id||'No registered widgets';$('note').textContent=primary?.text||((primary?.value??'')+'')||'empty';
 $('widgetIds').replaceChildren(...tree.widgets.map(w=>{const row=document.createElement('div');row.textContent=w.id+' · '+(w.text??(w.value!==undefined?w.value:w.checked?'on':'off'));return row}));
 if(data.build){themeLight=buildInfo.theme==='light';$('light').checked=themeLight;$('light').disabled=!buildInfo.light_available;$('light').title=buildInfo.light_available?'Switch tested palettes':'Only the selected palette is available for this interface';$('themeName').textContent=themeLight?'Light theme':'Dark theme';
 $('boardReady').textContent=buildInfo.testing?'Testing candidate · '+buildInfo.progress:buildInfo.ready_for_board?'Ready for real board · source '+buildInfo.source_sha256.slice(0,12)+' · board theme: '+buildInfo.board_theme:buildInfo.source_sha256?'Showing last tested build. Source changed or a new build is pending.':'Alphabet demo · generate in chat to test a new UI.';
 $('boardCommand').hidden=!buildInfo.ready_for_board;}
 const screen=buildInfo.screen||'';
 $('connection').textContent=screen?('LVGL host connected · '+screen):'LVGL host connected';
 $('status').textContent=buildInfo.testing?buildInfo.progress:'Live framebuffer · 240 × 320 RGB565 · '+(themeLight?'Light':'Dark')+(screen?' · '+screen:'');
 if(screen&&screen!==drawFrame.screen){drawFrame.screen=screen;toast(screen)}
 if(data.saved)toast('Saved framebuffer PNG + widget tree: '+data.saved);
}
function command(data){const task=serial.then(async()=>{const result=await window.bench.command(data);drawFrame(result);return result});serial=task.catch(e=>{$('connection').textContent='Host error';$('status').textContent=e.message;toast(e.message)});return task}
function resize(){let w=area.clientWidth,h=area.clientHeight;if(cameraMode){w=Math.min(w,h*4/3);h=w*3/4}renderer.setSize(w,h);eye.aspect=w/h;eye.updateProjectionMatrix();const b=renderer.domElement.getBoundingClientRect(),p=viewport.getBoundingClientRect();Object.assign($('glareLayer').style,{left:(b.left-p.left)+'px',top:(b.top-p.top)+'px',width:b.width+'px',height:b.height+'px'})}
new ResizeObserver(resize).observe(area);
function setCamera(enabled){
 if(enabled===cameraMode)return;cameraMode=enabled;
 if(enabled){savedView={pos:eye.position.clone(),target:orbit.target.clone(),fov:eye.fov};orbit.enabled=false;webcam.visible=false;eye.position.copy(lensPos);eye.up.set(0,0,-1);eye.fov=14;eye.lookAt(gx,glassY,gz)}
 else{webcam.visible=true;eye.up.set(0,1,0);eye.fov=savedView.fov;eye.position.copy(savedView.pos);orbit.target.copy(savedView.target);orbit.enabled=true;orbit.update()}
 viewport.classList.toggle('camera',enabled);$('camera').hidden=enabled;$('back').hidden=!enabled;$('cameraControls').hidden=!enabled;
 $('viewName').textContent=enabled?'CAMERA SEAT · 4:3':'WALK-AROUND';$('viewDetail').textContent=enabled?'From the lens · framing is illustrative':'Drag to orbit · scroll to dolly';
 updateEffects();resize();
}
function updateEffects(){renderer.domElement.style.filter=cameraMode?`blur(${$('focus').value}px)`:'none';$('focusValue').textContent=+$('focus').value===0?'Sharp':'Soft';$('glareLayer').style.display=cameraMode&&$('glare').checked?'block':'none'}
function home(){if(cameraMode)setCamera(false);eye.fov=42;eye.position.set(.86,1.40,1.15);orbit.target.set(.02,.88,-.03);orbit.update();resize()}
function inspect(){if(cameraMode)setCamera(false);eye.fov=42;eye.position.set(.23,.89,.035);orbit.target.set(gx,.75,gz);orbit.update();resize()}
$('camera').onclick=()=>setCamera(true);$('back').onclick=()=>setCamera(false);$('home').onclick=home;$('close').onclick=inspect;
$('focus').oninput=updateEffects;$('glare').onchange=updateEffects;
$('light').onchange=async()=>{const previous=themeLight;themeLight=$('light').checked;try{await command({action:'theme',light:themeLight});$('themeName').textContent=themeLight?'Light theme':'Dark theme'}catch{themeLight=previous;$('light').checked=previous}};
$('reset').onclick=()=>command({action:'reset'});$('capture').onclick=()=>command({action:'capture'});
$('chat').onclick=()=>window.bench.openChat();
function hitAt(clientX,clientY){const b=renderer.domElement.getBoundingClientRect();mouse.set((clientX-b.left)/b.width*2-1,-(clientY-b.top)/b.height*2+1);ray.setFromCamera(mouse,eye);return ray.intersectObject(glass)[0]}
let down=null;
let sliderDrag=null,dragPending=null,dragBusy=false;
function sliderValue(hit){const w=sliderDrag.widget,r=sliderDrag.range,x=hit.uv.x*240,y=(1-hit.uv.y)*320;const fraction=w.w>=w.h?(x-w.x)/(w.w-1):(w.y+w.h-1-y)/(w.h-1);return Math.round(r.min+Math.max(0,Math.min(1,fraction))*(r.max-r.min))}
async function sendDrag(){if(dragBusy)return;dragBusy=true;try{while(dragPending){const next=dragPending;dragPending=null;await command({action:'drag',...next})}}catch{}finally{dragBusy=false}}
function queueDrag(hit){dragPending={id:sliderDrag.widget.id,value:sliderValue(hit)};sendDrag()}
renderer.domElement.addEventListener('pointerdown',e=>{
 if(e.button!==0)return;const hit=hitAt(e.clientX,e.clientY);if(!hit)return;
 const x=hit.uv.x*240,y=(1-hit.uv.y)*320;
 const widget=tree?.widgets.find(w=>w.type==='slider'&&w.visible&&!w.disabled&&x>=w.x-6&&x<=w.x+w.w+6&&y>=w.y-10&&y<=w.y+w.h+10);
 const range=widget&&ranges.find(r=>r.x===widget.x&&r.y===widget.y&&r.w===widget.w&&r.h===widget.h);
 if(widget&&range){e.stopImmediatePropagation();renderer.domElement.focus();renderer.domElement.setPointerCapture(e.pointerId);sliderDrag={widget,range};orbit.enabled=false;down=null;queueDrag(hit)}
},true);
renderer.domElement.addEventListener('pointermove',e=>{if(sliderDrag){e.stopImmediatePropagation();const hit=hitAt(e.clientX,e.clientY);if(hit)queueDrag(hit)}},true);
renderer.domElement.addEventListener('pointerup',e=>{if(sliderDrag){e.stopImmediatePropagation();const hit=hitAt(e.clientX,e.clientY);if(hit)queueDrag(hit);sliderDrag=null;orbit.enabled=!cameraMode;renderer.domElement.releasePointerCapture(e.pointerId)}},true);
renderer.domElement.addEventListener('pointercancel',()=>{sliderDrag=null;down=null;orbit.enabled=!cameraMode});
renderer.domElement.addEventListener('pointerdown',e=>{renderer.domElement.focus();if(e.button===0)down={x:e.clientX,y:e.clientY};});
renderer.domElement.addEventListener('pointerup',e=>{if(e.button!==0||!down)return;const moved=Math.hypot(e.clientX-down.x,e.clientY-down.y);down=null;if(moved>4)return;const hit=hitAt(e.clientX,e.clientY);if(hit)command({action:'tap',x:Math.min(239,Math.floor(hit.uv.x*240)),y:Math.min(319,Math.floor((1-hit.uv.y)*320))})});
renderer.domElement.addEventListener('contextmenu',e=>e.preventDefault());
renderer.domElement.addEventListener('keydown',e=>{if(['KeyW','KeyA','KeyS','KeyD'].includes(e.code)){keys.add(e.code);e.preventDefault()}});
window.addEventListener('keyup',e=>keys.delete(e.code));window.addEventListener('blur',()=>keys.clear());
function walk(dt){if(cameraMode||!keys.size)return;const forward=new THREE.Vector3();eye.getWorldDirection(forward);forward.y=0;forward.normalize();const right=new THREE.Vector3().crossVectors(forward,new THREE.Vector3(0,1,0));const move=new THREE.Vector3();if(keys.has('KeyW'))move.add(forward);if(keys.has('KeyS'))move.sub(forward);if(keys.has('KeyD'))move.add(right);if(keys.has('KeyA'))move.sub(right);if(move.lengthSq())move.normalize().multiplyScalar(dt*.32);eye.position.add(move);orbit.target.add(move);const dy=.97-eye.position.y;eye.position.y=.97;orbit.target.y=Math.max(.74,orbit.target.y+dy);}
let last=performance.now();function animate(t){const dt=Math.min((t-last)/1000,.05);last=t;walk(dt);if(!cameraMode)orbit.update();renderer.render(scene,eye);requestAnimationFrame(animate)}requestAnimationFrame(animate);
window.bench.onExit(code=>{running=false;$('connection').textContent='LVGL stopped';$('status').textContent='Host process exited: '+code});
await command({action:'frame'});
// Poll the same buffer, so LVGL timers/animations remain live even without taps.
let pollBusy=false;setInterval(()=>{if(running&&!pollBusy&&!dragBusy){pollBusy=true;command({action:'frame'}).catch(()=>{}).finally(()=>pollBusy=false)}},200);
// Integration checks use the same raycast + renderer + process as desktop users.
window.benchTest={pose(){return {position:eye.position.toArray(),target:orbit.target.toArray(),distance:eye.position.distanceTo(orbit.target)}},keyPoint(id){
 const w=tree.widgets.find(w=>w.id===id);const p=glass.localToWorld(new THREE.Vector3(((w.x+w.w/2)/240-.5)*.0432,(.5-(w.y+w.h/2)/320)*.0576,0));p.project(eye);const b=renderer.domElement.getBoundingClientRect();return {x:Math.round(b.left+(p.x+1)*b.width/2),y:Math.round(b.top+(1-p.y)*b.height/2)};
},view(name){$('focus').value='0';$('glare').checked=false;if(name==='camera')setCamera(true);else if(name==='whole-bench')home();else inspect();updateEffects();renderer.render(scene,eye)},async run(){
 const checks={};await command({action:'reset'});setCamera(true);renderer.render(scene,eye);
 const key=tree.widgets.find(w=>w.id==='key_a');
 const p=glass.localToWorld(new THREE.Vector3(((key.x+key.w/2)/240-.5)*.0432,(.5-(key.y+key.h/2)/320)*.0576,0));p.project(eye);
 const b=renderer.domElement.getBoundingClientRect();const hit=hitAt(b.left+(p.x+1)*b.width/2,b.top+(1-p.y)*b.height/2);
 checks.raycast=!!hit;await command({action:'tap',x:Math.floor(hit.uv.x*240),y:Math.floor((1-hit.uv.y)*320)});
 checks.clickedNote=tree.widgets.find(w=>w.id==='lbl_note').text==='A';
 checks.cameraAspect=Math.abs(eye.aspect-4/3)<.001;checks.cameraAtLens=eye.position.distanceTo(lensPos)<1e-7;
 await command({action:'theme',light:true});checks.themePreservesState=tree.widgets.find(w=>w.id==='lbl_note').text==='A';
 await command({action:'theme',light:false});checks.nearest=tex.magFilter===THREE.NearestFilter&&tex.minFilter===THREE.NearestFilter;
 $('focus').value='3';updateEffects();checks.cameraBlur=renderer.domElement.style.filter==='blur(3px)';
 setCamera(false);checks.glassSharp=renderer.domElement.style.filter==='none';
 const before=eye.position.clone();keys.add('KeyW');walk(.2);keys.clear();checks.walk=eye.position.distanceTo(before)>.01&&eye.position.y===.97;
 inspect();renderer.render(scene,eye);checks.noGLError=renderer.getContext().getError()===0;
 if(Object.values(checks).some(x=>!x))throw Error(JSON.stringify(checks));return checks;
}};
window.pipelineTest={
 snapshot(){return {tree,build:buildInfo,ranges}},
 async action(data){return await command(data)},
 async idle(){for(let i=0;i<160&&(dragBusy||dragPending);i++)await new Promise(r=>setTimeout(r,50));await serial},
 point(id,fraction=.5){const w=tree.widgets.find(w=>w.id===id);const x=w.x+(w.w-1)*(w.w>=w.h?fraction:.5),y=w.y+(w.h-1)*(w.w>=w.h?.5:1-fraction);
  const p=glass.localToWorld(new THREE.Vector3((x/240-.5)*.0432,(.5-y/320)*.0576,0));p.project(eye);const b=renderer.domElement.getBoundingClientRect();return {x:Math.round(b.left+(p.x+1)*b.width/2),y:Math.round(b.top+(1-p.y)*b.height/2)}}
};
