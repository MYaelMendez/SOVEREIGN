// VSCODER://BRIDGE — Node.js crypto shim for browser/webview context
// Provides createHash, createHmac, randomBytes, timingSafeEqual
(function() {
  const subtle = globalThis.crypto?.subtle;
  
  function toHex(buffer) {
    return Array.from(new Uint8Array(buffer))
      .map(b => b.toString(16).padStart(2, '0'))
      .join('');
  }
  
  function fromHex(hex) {
    const bytes = new Uint8Array(hex.length / 2);
    for (let i = 0; i < hex.length; i += 2) {
      bytes[i / 2] = parseInt(hex.substr(i, 2), 16);
    }
    return bytes;
  }
  
  async function sha256(data) {
    const encoder = new TextEncoder();
    const buffer = encoder.encode(typeof data === 'string' ? data : JSON.stringify(data));
    const hashBuffer = await subtle.digest('SHA-256', buffer);
    return toHex(hashBuffer);
  }
  
  async function hmacSha256(key, data) {
    const encoder = new TextEncoder();
    const keyBuffer = encoder.encode(key);
    const dataBuffer = encoder.encode(typeof data === 'string' ? data : JSON.stringify(data));
    const cryptoKey = await subtle.importKey('raw', keyBuffer, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
    const signatureBuffer = await subtle.sign('HMAC', cryptoKey, dataBuffer);
    return toHex(signatureBuffer);
  }
  
  function randomBytes(count) {
    const bytes = new Uint8Array(count);
    globalThis.crypto.getRandomValues(bytes);
    return bytes;
  }
  
  function timingSafeEqual(a, b) {
    if (a.length !== b.length) return false;
    let result = 0;
    for (let i = 0; i < a.length; i++) {
      result |= a[i] ^ b[i];
    }
    return result === 0;
  }
  
  const createHash = (algorithm) => ({
    update(data) { this._data = (this._data || '') + data; return this; },
    digest(encoding) { return sha256(this._data).then(h => encoding === 'hex' ? h : fromHex(h)); }
  });
  
  const createHmac = (algorithm, key) => ({
    update(data) { this._data = (this._data || '') + data; return this; },
    digest(encoding) { return hmacSha256(key, this._data).then(h => encoding === 'hex' ? h : fromHex(h)); }
  });
  
  globalThis.crypto = globalThis.crypto || {};
  globalThis.crypto.subtle = subtle;
  globalThis.crypto.createHash = createHash;
  globalThis.crypto.createHmac = createHmac;
  globalThis.crypto.randomBytes = randomBytes;
  globalThis.crypto.timingSafeEqual = timingSafeEqual;
  globalThis.crypto.getRandomValues = globalThis.crypto.getRandomValues || function(arr) {
    for (let i = 0; i < arr.length; i++) arr[i] = Math.floor(Math.random() * 256);
    return arr;
  };
})();
