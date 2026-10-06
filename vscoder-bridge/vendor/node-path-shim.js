// VSCODER://BRIDGE — Node.js path shim for browser/webview context
(function() {
  globalThis.path = globalThis.path || {};
  globalThis.path.join = (...parts) => parts.join('/').replace(/\/+/g, '/');
  globalThis.path.dirname = (p) => p.split('/').slice(0, -1).join('/') || '/';
  globalThis.path.basename = (p) => p.split('/').pop() || '';
  globalThis.path.extname = (p) => {
    const base = p.split('/').pop() || '';
    const idx = base.lastIndexOf('.');
    return idx >= 0 ? base.slice(idx) : '';
  };
  globalThis.path.resolve = (...parts) => parts.join('/').replace(/\/+/g, '/');
  globalThis.path.relative = (from, to) => to;
  globalThis.path.sep = '/';
})();
