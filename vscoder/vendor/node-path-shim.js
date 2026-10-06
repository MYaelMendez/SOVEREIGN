// VSCODER:// node-path-shim.js — Browser path shim
export function join(...paths: string[]): string {
  return paths.join('/').replace(/\/+/g, '/');
}

export function dirname(path: string): string {
  return path.split('/').slice(0, -1).join('/') || '/';
}

export function basename(path: string): string {
  return path.split('/').pop() || '';
}

export function extname(path: string): string {
  const base = basename(path);
  const idx = base.lastIndexOf('.');
  return idx >= 0 ? base.slice(idx) : '';
}

export default { join, dirname, basename, extname };