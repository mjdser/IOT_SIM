const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('bench',{command:data=>ipcRenderer.invoke('bench-command',data),openChat:()=>ipcRenderer.invoke('open-chat'),onExit:fn=>ipcRenderer.on('host-exit',(_,code)=>fn(code))});
