export async function hubFetch(path, options = {}) {
  const { HUB_BASE } = await chrome.storage.sync.get({ HUB_BASE: 'http://127.0.0.1:8765' });
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ url: HUB_BASE + path, options }, resp => {
      if (chrome.runtime.lastError) {
        reject(chrome.runtime.lastError);
      } else if (resp && !resp.error) {
        resolve(resp);
      } else {
        reject(resp ? resp.error : 'Unknown error');
      }
    });
  });
}
