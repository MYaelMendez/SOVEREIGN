// VSCODER:// node-crypto-shim.js — Browser crypto shim
// Provides SHA-256 hashing in the browser using Web Crypto API

export function createHash(algorithm: string) {
  let data = '';
  return {
    update(chunk: string) { data += chunk; return this; },
    async digest(encoding: string): Promise<string> {
      const encoder = new TextEncoder();
      const buffer = await crypto.subtle.digest(algorithm, encoder.encode(data));
      const bytes = new Uint8Array(buffer);
      if (encoding === 'hex') {
        return Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
      }
      return String.fromCharCode(...bytes);
    },
  };
}

export function createHmac(algorithm: string, key: string) {
  return createHash(algorithm);
}

export function timingSafeEqual(a: Buffer, b: Buffer): boolean {
  if (a.length !== b.length) return false;
  let result = 0;
  for (let i = 0; i < a.length; i++) result |= a[i] ^ b[i];
  return result === 0;
}

export function randomBytes(size: number): Buffer {
  const bytes = new Uint8Array(size);
  crypto.getRandomValues(bytes);
  return Buffer.from(bytes);
}

export default { createHash, createHmac, timingSafeEqual, randomBytes };