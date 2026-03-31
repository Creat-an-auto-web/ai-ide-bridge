const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('aiIdeDesktop', {
  async getInitialState() {
    return await ipcRenderer.invoke('ai-ide-desktop:get-initial-state')
  },
  async pickDirectory() {
    return await ipcRenderer.invoke('ai-ide-desktop:pick-directory')
  },
  async pickFile() {
    return await ipcRenderer.invoke('ai-ide-desktop:pick-file')
  },
})
