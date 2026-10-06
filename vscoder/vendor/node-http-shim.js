// VSCODER:// node-http-shim.js — Browser fetch shim
// Provides a simple HTTP interface using fetch API

export function createServer(handler: (req: any, res: any) => void) {
  return {
    listen(port: number, callback?: () => void) {
      console.log(`HTTP server would listen on :${port}`);
      callback?.();
    },
    close() {},
  };
}

export default { createServer };