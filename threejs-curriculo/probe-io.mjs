import { spawn } from 'node:child_process';
// Launch Chrome to capture the page and evaluate __renderFrame
const chrome = spawn('C:/Users/yaelm/AppData/Local/hermes/tools/node-26.7.0-win32-x64/node.exe', [
  'script.mjs'
], { stdio: 'inherit' });
