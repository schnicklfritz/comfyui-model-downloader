javascript:(function(){
    const entries = performance.getEntriesByType('resource');
    const modelExts = /\.(safetensors|ckpt|pt|pth|bin)(\?|$)/i;
    const models = entries.filter(e => modelExts.test(e.name));
    
    if (models.length === 0) {
        alert('❌ No model downloads detected.\n\nStart a download first, then click this bookmarklet.');
        return;
    }
    
    const url = models[models.length - 1].name;
    const filename = url.split('?')[0].split('/').pop();
    
    // Save to localStorage for ComfyUI to pick up
    localStorage.setItem('comfyui_download_url', url);
    localStorage.setItem('comfyui_download_filename', filename);
    
    // Also copy to clipboard
    navigator.clipboard.writeText(url).then(() => {
        alert(`✓ Captured: ${filename}\n\nURL copied to clipboard!\n\nPaste into ComfyUI Cloud Model Downloader node.`);
    }).catch(() => {
        prompt('Copy this URL to ComfyUI node:', url);
    });
})();
