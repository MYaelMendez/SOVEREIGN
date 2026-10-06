// VSCODER://BRIDGE — Node.js child_process shim for browser/webview context
(function() {
  globalThis.child_process = globalThis.child_process || {};
  globalThis.child_process.exec = (cmd, opts, cb) => {
    if (typeof opts === 'function') { cb = opts; opts = {}; }
    cb(null, '', '');
  };
  globalThis.child_process.execSync = (cmd) => '';
  globalThis.child_process.spawn = (cmd, args) => ({
    stdout: { on: () => {} },
    stderr: { on: () => {} },
    on: () => {},
    kill: () => {}
  });
})();
