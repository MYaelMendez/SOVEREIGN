// VSCODER:// node-fs-shim.js — Browser storage shim
// Provides file system-like interface using localStorage

export function existsSync(path: string): boolean {
  return localStorage.getItem(`fs:${path}`) !== null;
}

export function readFileSync(path: string, encoding: string = 'utf8'): string {
  const data = localStorage.getItem(`fs:${path}`);
  if (data === null) throw new Error(`ENOENT: no such file or directory, '${path}'`);
  return data;
}

export function writeFileSync(path: string, data: string, encoding: string = 'utf8'): void {
  localStorage.setItem(`fs:${path}`, data);
}

export function mkdirSync(path: string, options?: any): void {
  localStorage.setItem(`fs:${path}:dir`, 'true');
}

export function statSync(path: string): { isDirectory: () => boolean; isFile: () => boolean } {
  return {
    isDirectory: () => localStorage.getItem(`fs:${path}:dir`) === 'true',
    isFile: () => localStorage.getItem(`fs:${path}`) !== null,
  };
}

export default { existsSync, readFileSync, writeFileSync, mkdirSync, statSync };