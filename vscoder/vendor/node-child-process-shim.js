// VSCODER:// node-child-process-shim.js — Browser child_process shim
export function execSync(command: string, options?: any): string {
  console.log(`Would execute: ${command}`);
  return '';
}

export function exec(command: string, options: any, callback: Function): void {
  callback(null, '', '');
}

export default { execSync, exec };