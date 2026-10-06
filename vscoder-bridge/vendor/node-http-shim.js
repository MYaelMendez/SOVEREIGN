// VSCODER://BRIDGE — Node.js http shim for browser/webview context
(function() {
  globalThis.http = globalThis.http || {};
  globalThis.https = globalThis.https || {};
  
  function createServer(handler) {
    return {
      listen(port, cb) { if (cb) cb(); },
      close() {},
      on() {}
    };
  }
  
  globalThis.http.createServer = createServer;
  globalThis.https.createServer = createServer;
  globalThis.http.get = (url, cb) => {
    fetch(url).then(r => cb({ statusCode: r.status, on: (ev, h) => {} }));
  };
  globalThis.https.get = globalThis.http.get;
})();
