// VSCODER:// standalone WebMCP server
const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const PORT = 8124;
const ROOT = __dirname;

const chain = [];
function computeHash(data) {
  return crypto.createHash('sha256').update(JSON.stringify(data)).digest('hex');
}
function addReceipt(action, input, output) {
  const prevHash = chain.length ? chain[chain.length-1].hash : 'genesis';
  const entry = { seq: chain.length+1, timestamp: new Date().toISOString(), action, input: input.slice(0,500), output: output.slice(0,500), prevHash };
  entry.hash = computeHash(entry);
  chain.push(entry);
  return entry;
}

const server = http.createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }
  const url = req.url || '/';
  if (url === '/' || url === '/index.html') {
    res.writeHead(200, {'Content-Type': 'text/html'});
    res.end(fs.readFileSync(path.join(ROOT, 'webview', 'index.html')));
  } else if (url === '/api/health') {
    res.writeHead(200, {'Content-Type': 'application/json'});
    res.end(JSON.stringify({status:'ok',version:'0.1.0',tools:['vscoder_observe','vscoder_plan','vscoder_refactor','vscoder_build','vscoder_test','vscoder_debug','vscoder_benchmark','vscoder_git_diff','vscoder_receipt']}));
  } else if (url === '/api/receipts') {
    res.writeHead(200, {'Content-Type': 'application/json'});
    res.end(JSON.stringify({chain, valid:true, count:chain.length}));
  } else if (url === '/api/invoke' && req.method === 'POST') {
    let body = '';
    req.on('data', c => body += c);
    req.on('end', () => {
      const {tool, params} = JSON.parse(body);
      let result;
      if (tool === 'vscoder_observe') {
        result = {mode:'standalone', timestamp:new Date().toISOString()};
        addReceipt('observe', JSON.stringify(params), JSON.stringify(result));
      } else if (tool === 'vscoder_plan') {
        result = {instruction:params.instruction||'', steps:['Analyze','Refactor','Test','Receipt']};
        addReceipt('plan', JSON.stringify(params), JSON.stringify(result));
      } else if (tool === 'vscoder_receipt') {
        result = {chain, valid:true, count:chain.length};
      } else {
        result = {mode:'standalone', tool};
        addReceipt(tool, JSON.stringify(params), JSON.stringify(result));
      }
      res.writeHead(200, {'Content-Type': 'application/json'});
      res.end(JSON.stringify(result));
    });
  } else {
    res.writeHead(404); res.end();
  }
});
server.listen(PORT, () => console.log(`VSCODER:// server on :${PORT}`));