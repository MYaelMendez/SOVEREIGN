// Verify the rebuilt three.global.js exposes all THREE members needed by markets.html
const vm = require('vm');
const fs = require('fs');

const code = fs.readFileSync('C:/æ/site/vendor/three.global.js', 'utf8');

const sandbox = {
  window: {},
  self: {},
  navigator: { gpu: null, userAgent: 'node-test' },
  document: { createElement: () => ({ getContext: () => null, style: {} }), addEventListener: () => {} },
  performance: { now: () => Date.now() },
  console: console,
  Image: class Image {},
  URL: { createObjectURL: () => '', revokeObjectURL: () => {} },
};
sandbox.window = sandbox;
sandbox.self = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);

try {
  vm.runInContext(code, sandbox, { timeout: 30000 });
  const THREE = sandbox.THREE;
  console.log('typeof THREE:', typeof THREE);
  console.log('REVISION:', THREE?.REVISION);

  const checks = [
    'Scene','PerspectiveCamera','WebGLRenderer','FogExp2','Fog','Controls','OrbitControls',
    'BufferGeometry','BufferAttribute','PointsMaterial','Points','MeshBasicMaterial',
    'MeshStandardMaterial','IcosahedronGeometry','TorusGeometry','SphereGeometry','PlaneGeometry',
    'BoxGeometry','ConeGeometry','CylinderGeometry','Vector2','Vector3','Vector4','Matrix4',
    'Quaternion','Spherical','Ray','MathUtils','AmbientLight','DirectionalLight','PointLight',
    'HemisphereLight','SpotLight','CanvasTexture','WebGLRenderTarget','Color','Texture',
    'SRGBColorSpace','AdditiveBlending','LinearFilter','NearestFilter','RepeatWrapping',
    'MirroredRepeatWrapping','EventDispatcher','Clock','LoadingManager','TextureLoader',
    'Raycaster','Sprite','SpriteMaterial','Group','Mesh','MOUSE','TOUCH',
    'WebGLCoordinateSystem','FrontSide','BackSide','DoubleSide','NoColorSpace','NormalBlending',
    'InstancedMesh','LOD','Box2','Box3','Reverser','LinearTransfer',
  ];

  let allOk = true;
  for (const name of checks) {
    const v = THREE && THREE[name];
    const ok = v !== undefined && v !== null;
    if (!ok) allOk = false;
    console.log('  THREE.' + name + ': ' + (ok ? 'PASS' : 'FAIL') + ' typeof=' + (ok ? typeof v : 'n/a'));
  }

  const hasStr = code.includes('this.setAnimationLoop = function');
  console.log('  this.setAnimationLoop:', hasStr ? 'PASS (instance method)' : 'FAIL');

  if (THREE.OrbitControls) {
    console.log('  OrbitControls is function:', typeof THREE.OrbitControls === 'function');
    const ocProto = Object.getPrototypeOf(THREE.OrbitControls);
    console.log('  OrbitControls extends:', ocProto ? (ocProto.name || 'class') : 'unknown');
  } else {
    console.log('  OrbitControls: FAIL');
    allOk = false;
  }

  console.log('  THREE.WebGPURenderer:', THREE.WebGPURenderer ? 'present (unexpected)' : 'absent (correct)');
  console.log('  THREE.ConeGeometry:', THREE.ConeGeometry ? 'PASS' : 'FAIL');
  console.log('\n' + (allOk ? 'ALL CHECKS PASSED' : 'SOME CHECKS FAILED'));
} catch (e) {
  console.error('ERROR:', e.message);
  console.error(e.stack?.split('\n').slice(0, 10).join('\n'));
}
