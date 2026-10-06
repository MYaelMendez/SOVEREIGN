// VSCODER://BRIDGE — Node.js fs shim for browser/webview context
(function() {
  const _files = new Map();
  
  globalThis.fs = globalThis.fs || {};
  globalThis.fs.existsSync = (path) => _files.has(path);
  globalThis.fs.readFileSync = (path, encoding) => {
    const content = _files.get(path);
    if (content === undefined) throw new Error('ENOENT: ' + path);
    return encoding === 'utf8' ? content : Buffer.from(content);
  };
  globalThis.fs.writeFileSync = (path, content) => { _files.set(path, String(content)); };
  globalThis.fs.mkdirSync = (path, opts) => { _files.set(path + '/.dir', ''); };
  globalThis.fs.readdirSync = (path) => [];
  globalThis.fs.statSync = (path) => ({
    isDirectory: () => _files.has(path + '/.dir'),
    isFile: () => _files.has(path) && !_files.has(path + '/.dir'),
    size: (_files.get(path) || '').length
  });
  globalThis.fs.unlinkSync = (path) => { _files.delete(path); };
  globalThis.fs.appendFileSync = (path, content) => {
    const existing = _files.get(path) || '';
    _files.set(path, existing + content);
  };
})();
