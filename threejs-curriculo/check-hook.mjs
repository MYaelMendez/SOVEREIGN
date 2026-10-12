import { spawn } from 'node:child_process';

const chrome = spawn('C:/Users/yaelm/AppData/Local/hermes/tools/node-26.7.0-win32-x64/node.exe', [
  'C:/æ/threejs-curriculo/check-page.mjs'
], { stdio: 'inherit' });
