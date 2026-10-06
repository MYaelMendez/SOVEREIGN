/**
 * ThreeVideoPlayer — wraps an HTML5 <video> onto Three.js meshes
 * as a VideoTexture. Provides play/pause/volume/mute/seek controls
 * that work inside a WebGL/WebGPU canvas.
 *
 * Part of the æ:// mesh — gold-on-void, local-first, no CDN.
 *
 * Usage (non-module / global):
 *   <script src="../vendor/three.global.js"></script>
 *   <script src="three-video-player.js"></script>
 *   // THREE and ThreeVideoPlayer are available globally
 *
 *   const player = new ThreeVideoPlayer({
 *     src: '/aipodcast_me/fleet-waves-development.mp4',
 *     geometry: new THREE.PlaneGeometry(8, 4.5),
 *     loop: true,
 *     muted: true,
 *   });
 *   player.play();
 *   scene.add(player.mesh);
 */

class ThreeVideoPlayer {
  /**
   * @param {Object} opts
   * @param {string}  opts.src        Video source URL (cross-origin safe)
   * @param {THREE.BufferGeometry} [opts.geometry]  Defaults to PlaneGeometry(8, 4.5)
   * @param {THREE.Material}    [opts.material]   Material override; if omitted, a MeshBasicMaterial with the video texture is created
   * @param {boolean} [opts.loop=true]       Loop video
   * @param {boolean} [opts.muted=true]      Start muted (required for autoplay)
   * @param {boolean} [opts.autoplay=false]  Auto-start playback
   * @param {boolean} [opts.crossOrigin=true]  Set crossOrigin='anonymous'
   */
  constructor(opts = {}) {
    const {
      src,
      geometry = null,
      material = null,
      loop = true,
      muted = true,
      autoplay = false,
      crossOrigin = true,
    } = opts;

    // ── HTML5 video element ──
    this.video = document.createElement('video');
    this.video.src = src;
    this.video.loop = loop;
    this.video.muted = muted;
    this.video.playsInline = true;
    this.video.preload = 'auto';
    if (crossOrigin) this.video.crossOrigin = 'anonymous';
    if (autoplay) this.video.autoplay = true;

    // ── Video texture (THREE.VideoTexture) ──
    // Format defaults to RGBFormat in r170; the texture updates automatically
    // each render by sampling the current video frame.
    this.texture = new THREE.VideoTexture(this.video);
    this.texture.minFilter = THREE.LinearFilter;
    this.texture.magFilter = THREE.LinearFilter;
    this.texture.generateMipmaps = false;
    this.texture.colorSpace = THREE.SRGBColorSpace;

    // ── Geometry ──
    // Use PlaneBufferGeometry (deprecated alias for PlaneGeometry in r170,
    // but the name is kept for interface compatibility with the spec).
    this.geometry = geometry || new THREE.PlaneGeometry(8, 4.5, 1, 1);

    // ── Material ──
    if (material) {
      this.material = material;
      if (material.map !== this.texture) {
        this.material.map = this.texture;
      }
    } else {
      this.material = new THREE.MeshBasicMaterial({
        map: this.texture,
        side: THREE.DoubleSide,
        toneMapped: false,
      });
    }

    // ── Mesh ──
    this.mesh = new THREE.Mesh(this.geometry, this.material);
    this.mesh.name = 'ThreeVideoPlayer';

    // ── State tracking ──
    this._duration = 0;
    this._loaded = false;
    this.video.addEventListener('loadedmetadata', () => {
      this._duration = this.video.duration;
      this._loaded = true;
    });
  }

  // ═══ Playback control ═══════════════════════════════════════════════════

  /** Start playback. Resolves when the video actually plays. */
  async play() {
    try {
      await this.video.play();
      return true;
    } catch (e) {
      if (e instanceof Error) {
        console.warn('ThreeVideoPlayer.play:', e.message);
      } else {
        console.warn('ThreeVideoPlayer.play:', String(e));
      }
      return false;
    }
  }

  /** Pause playback. */
  pause() {
    this.video.pause();
  }

  /** Toggle play/pause. */
  toggle() {
    if (this.video.paused) {
      return this.play();
    } else {
      this.pause();
      return Promise.resolve(true);
    }
  }

  /** @param {number} v Volume 0–1 */
  setVolume(v) {
    this.video.volume = Math.max(0, Math.min(1, v));
  }

  /** @param {number} v Volume 0–1 (alias) */
  set volume(v) { this.video.volume = Math.max(0, Math.min(1, v)); }
  get volume() { return this.video.volume; }

  /** Mute the video. */
  mute() { this.video.muted = true; }

  /** Unmute the video. */
  unmute() { this.video.muted = false; }

  /** Toggle mute. */
  toggleMute() {
    this.video.muted = !this.video.muted;
    return this.video.muted;
  }

  /** @param {number} t Seconds to seek to. */
  seek(t) {
    if (this._loaded) this.video.currentTime = Math.max(0, t);
  }

  /** @param {number} rate e.g. 0.5, 1.0, 1.5, 2.0 */
  setPlaybackRate(rate) {
    this.video.playbackRate = rate;
  }

  /** @param {boolean} loop */
  set loop(v) { this.video.loop = v; }
  get loop() { return this.video.loop; }

  /** @returns {boolean} Currently playing? */
  get isPlaying() {
    return !this.video.paused && !this.video.ended;
  }

  /** @returns {number} Video duration in seconds (0 if not loaded). */
  get duration() {
    return this._duration;
  }

  /** @returns {number} Current playback time. */
  get currentTime() {
    return this.video.currentTime;
  }

  /** @returns {number} Playback rate. */
  get playbackRate() {
    return this.video.playbackRate;
  }

  // ═══ Deterministic rendering (for __renderFrame) ═══════════════════════

  /**
   * Seek to the frame that should be displayed at render step i/total.
   * Called by the CDP render harness's __renderFrame(i, total).
   *
   * @param {number} i     Current frame index (0-based)
   * @param {number} total Total number of frames
   * @param {number} [fps=30]  Frames per second for the target timeline
   */
  seekFrame(i, total, fps = 30) {
    if (this._duration === 0) {
      // Video metadata may not have loaded yet in headless Chrome
      // Try to get duration from the video element directly
      try { this._duration = this.video.duration || 0; } catch(e) {}
      if (this._duration === 0) return;
    }
    const duration = total / fps;
    const t = (i / Math.max(1, total - 1)) * duration;
    this.video.currentTime = t;
    // Mark texture for update
    if (this.texture) this.texture.needsUpdate = true;
  }

  /**
   * Force the video to a specific timestamp (for timeline-based animation).
   *
   * @param {number} t  Seconds
   */
  seekToTime(t) {
    this.seek(t);
    this.texture.needsUpdate = true;
  }

  // ═══ Timeline animation (compose with GSAP or manual) ══════════════════

  /**
   * Create a simple rotation/scale envelope around this player's mesh.
   * Pass a time parameter (0–1) and it will be applied.
   *
   * @param {number} t  Normalized time 0–1
   * @param {Object} [opts]
   * @param {number} [opts.rotationSpeed=1]  Radians per unit time
   * @param {number} [opts.scaleAmp=0.15]    Scale oscillation amplitude
   */
  applyTimeline(t, opts = {}) {
    const { rotationSpeed = 1, scaleAmp = 0.15 } = opts;
    const e = Math.PI * 2 * t;

    this.mesh.rotation.y = e * rotationSpeed * 0.3;
    this.mesh.rotation.x = Math.sin(e * 0.7) * 0.3;

    const s = 1 + Math.sin(e * 1.3) * scaleAmp;
    this.mesh.scale.setScalar(s);

    // Pulse emissive if using MeshStandardMaterial
    if (this.material.emissive !== undefined) {
      this.material.emissive.setHSL(t, 0.8, 0.5);
    }
  }

  // ═══ Disposal ═════════════════════════════════════════════════════════

  /** Dispose geometry, material, texture, and video. */
  dispose() {
    this.video.pause();
    this.video.removeAttribute('src');
    this.video.load();
    this.geometry.dispose();
    if (this.material) this.material.dispose();
    this.texture.dispose();
    if (this.mesh.parent) this.mesh.parent.remove(this.mesh);
  }

  /** @returns {THREE.Mesh} The mesh — for direct scene graph manipulation. */
  getObject3D() {
    return this.mesh;
  }
}

// ─── Convenience: create a video player on a named geometry ──────────────

/**
 * Factory: create a ThreeVideoPlayer and attach it to a specific geometry.
 *
 * @param {string} src   Video source URL
 * @param {string} shape  'plane' | 'box' | 'sphere' | 'torus' | 'cylinder' | 'ring'
 * @param {Object} [opts] Additional ThreeVideoPlayer options
 * @returns {ThreeVideoPlayer}
 */
function createVideoMesh(src, shape, opts = {}) {
  const geometryMap = {
    plane:    new THREE.PlaneGeometry(8, 4.5),
    box:      new THREE.BoxGeometry(4, 4, 4),
    sphere:   new THREE.SphereGeometry(3, 64, 32),
    torus:    new THREE.TorusGeometry(3, 1, 16, 100),
    cylinder: new THREE.CylinderGeometry(2, 2, 5, 32),
    ring:     new THREE.RingGeometry(2, 3, 64),
  };

  const geometry = geometryMap[shape] || geometryMap.plane;

  // For enclosed geometries (sphere, box), use DoubleSide so video is visible
  const material = new THREE.MeshBasicMaterial({
    map: null,  // will be set by the player
    side: THREE.DoubleSide,
    toneMapped: false,
  });

  return new ThreeVideoPlayer({
    src,
    geometry,
    material,
    ...opts,
  });
}

// ─── Export as global for non-module script tags ─────────────────────────

if (typeof window !== 'undefined') {
  window.ThreeVideoPlayer = ThreeVideoPlayer;
  window.createVideoMesh = createVideoMesh;
}
