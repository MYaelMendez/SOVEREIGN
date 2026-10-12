import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import url from 'node:url';

const ROOT = process.cwd();
const PORT = 8011;
const types = { '.html':'text/html', '.js':'text/javascript', '.mjs':'text/javascript', '.json':'application/json', '.css':'text/css' };
const reports = [];

const server = http.createServer((req, res) => {
  const u = url.parse(req.url, true);
  if (u.pathname === '/report') {
    reports.push(u.query.r || '');
    console.log('REPORT ' + (u.query.r || ''));
    res.writeHead(200, { 'content-type':'text/plain', 'access-control-allow-origin':'*' });
    res.end('ok');
    return;
  }
  let p = decodeURIComponent(u.pathname);
  if (p === '/') p = '/index.html';
  const fp = path.join(ROOT, p);
  if (!fp.startsWith(ROOT)) { res.writeHead(403); res.end('no'); return; }
  fs.readFile(fp, (err, buf) => {
    if (err) { res.writeHead(404); res.end('404'); return; }
    res.writeHead(200, { 'content-type': types[path.extname(fp)] || 'application/octet-stream' });
    res.end(buf);
  });
});
server.listen(PORT, '127.0.0.1', () => console.log('LISTEN ' + PORT));
