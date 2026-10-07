// Verify the rebuilt three.global.js exposes all needed members
const vm = require('vm');
const fs = require('fs');

const code = fs.readFileSync('C:/æ/site/vendor/three.global.js', 'utf8');

// Create a browser-like sandbox
const sandbox = {
  window: {},
  self: {},
  navigator: { gpu: null, userAgent: 'node-test' },
  document: { createElement: () => ({ getContext: () => null, style: {} }), addEventListener: () => {} },
  performance: { now: () => Date.now() },
  console: console,
};
sandbox.window = sandbox;  // window === global
sandbox.self = sandbox;
sandbox.globalThis = sandbox;

vm.createContext(sandbox);

try {
  vm.runInContext(code, sandbox, { timeout: 30000 });
  const THREE = sandbox.THREE;
  
  console.log('typeof THREE:', typeof THREE);
  console.log('REVISION:', THREE?.REVISION);
  
  const checks = [
    'Scene', 'PerspectiveCamera', 'WebGLRenderer', 'WebGPURenderer',
    'FogExp2', 'Fog', 'Controls', 'OrbitControls', 'Raycaster',
    'Vector2', 'Vector3', 'Color', 'Mesh', 'Group', 'Points',
    'BufferGeometry', 'BufferAttribute', 'PointsMaterial', 'MeshBasicMaterial',
    'MeshStandardMaterial', 'AmbientLight', 'DirectionalLight', 'PointLight',
    'Sprite', 'SpriteMaterial', 'CanvasTexture', 'SRGBColorSpace',
    'AdditiveBlending', 'IcosahedronGeometry', 'TorusGeometry', 'Quaternion',
    'Vector2', 'Spherical', 'Ray', 'MathUtils', 'MOUSE', 'TOUCH'
  ];
  
  let allOk = true;
  for (const name of checks) {
    const v = THREE && THREE[name];
    const ok = v !== undefined && v !== null;
    if (!ok) allOk = false;
    console.log(`  THREE.${name}: ${ok ? '✓' : '✗ MISSING'} ${ok ? typeof v : ''}`);
  }
  
  // Check WebGLRenderer has setAnimationLoop
  const hasSetAnim = THREE.WebGLRenderer && typeof THREE.WebGLRenderer.prototype?.setAnimationLoop === 'function';
  const hasSetAnim2 = THREE.WebGLRenderer?.prototype?.setAnimationLoop;
  console.log('WebGLRenderer.prototype.setAnimationLoop:', hasSetAnim ? '✓ function' : '✗ missing');
  
  // Check OrbitControls extends Controls
  if (THREE.OrbitControls) {
    const proto = Object.getPrototypeOf(THREE.OrbitControls);
    console.log('OrbitControls parent:', proto?.name || proto?.constructor?.name || 'unknown');
    console.log('OrbitControls is function:', typeof THREE.OrbitControls === 'function');
  }
  
  console.log('\n' + (allOk ? '✅ ALL CHECKS PASSED' : '❌ SOME CHECKS FAILED'));
} catch (e) {
  console.error('ERROR executing three.global.js:', e.message);
  console.error(e.stack?.split('\n').slice(0, 5).join('\n'));
}
