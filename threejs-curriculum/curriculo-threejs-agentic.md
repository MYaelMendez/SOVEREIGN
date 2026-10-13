# Agentic Electronic Engineering — Currículo Three.js

**Nivel:** De cero a world-class
**Duración:** 12 semanas (8-10 horas/semana)
**Prerrequisitos:** JavaScript intermedio, HTML/CSS básico, álgebra lineal básica
**Filosofía:** Humano dirige, agente ejecuta. Cada módulo termina en un artefacto verificable.

---

## Fase 1: Fundamentos de Rendering (Semanas 1-3)

### Semana 1: Pipeline y Matemáticas

| Día | Tema | Actividad | Verificación |
|---|---|---|---|
| 1 | Scene graph, transforms, matrices 4x4 | Escena con 50 cubos en jerarquía | Screenshot + 1 test |
| 2 | Quaterniones vs Euler | Demostrar gimbal lock y resolver con quaternions | Video 30s + código |
| 3 | Cámaras y frustum | Camera switcher (perspective ↔ orthographic) | Interacción web |
| 4 | Raycasting y picking | Raycast contra 100 objetos, highlight en hover | Evento mouse funcional |
| 5 | Coordenadas y espacios | Visualizar transformaciones space-to-space | Debug visual |
| 6 | BufferGeometry | Geometría custom desde cero | 2 geometry views |
| 7 | Repaso y proyecto mini | Escena interactiva con todos los conceptos | Deploy local |

**Entregable:** `fase1-fundamentos.html` — escena con 50 cubos, cámara orbital, raycasting.

### Semana 2: Geometría y Atributos

| Día | Tema | Actividad | Verificación |
|---|---|---|---|
| 1 | BufferGeometry attributes | Custom geometry con position, normal, uv | Wireframe view |
| 2 | Index geometry | Comparar memoria: indexed vs non-indexed | Benchmark |
| 3 | Morph targets | Animar geometría con morph targets | Morph slider |
| 4 | Generación procedural | Terreno con ruido Perlin | Configuración reproducible |
| 5 | Merging y batching | Batch 1000 meshes estáticos | FPS counter |
| 6 | InstancedMesh básico | 1000 instancias con transform único | Transform controls |
| 7 | LOD manual | Comparar 5 aproximaciones a LOD | Performance chart |

**Entregable:** `fase2-geometria.html` — terreno interactivo con 1000 instancias.

### Semana 3: Materiales y Texturas

| Día | Tema | Actividad | Verificación |
|---|---|---|---|
| 1 | MeshStandardMaterial vs Phong | Comparativa visual lado a lado | Screenshots |
| 2 | Texturas y UV mapping | Aplicar 5 tipos de texturas | UV editor visual |
| 3 | Environment maps (IBL) | HDRIs y reflections realistas | Reflection demo |
| 4 | Texture atlases | Optimizar 10 texturas → 1 atlas | Memory profiler |
| 5 | onBeforeCompile | Modificar shader de material estándar | Shader injection visible |
| 6 | Material caching | Evitar recompilaciones | Recompilation counter |
| 7 | Biblioteca de materiales | 10 materiales reutilizables | Export/import API |

**Entregable:** `fase3-materiales.html` — comparativa de materiales con IBL.

---

## Fase 2: Shaders y GLSL (Semanas 4-6)

### Semana 4: Shader Foundations

| Día | Tema | Actividad | Verificación |
|---|---|---|---|
| 1 | Vertex y fragment shaders | Shader mínimo: color plano | Compile OK |
| 2 | Uniforms | Pasar tiempo, resolución, mouse | Interactivo |
| 3 | Attributes | Pasar posición custom | Visualización |
| 4 | Varyings | Interpolación vertex/fragment | Smooth shading |
| 5 | ShaderMaterial | Reemplazar material estándar | Funcionalidad equivalente |
| 6 | Three.js shader chunks | Incluir chunks en shaders custom | Code reuse |
| 7 | Debugging | Shader errors + Spector.js | Debug console |

**Recurso:** [The Book of Shaders](https://thebookofshaders.com/)

**Entregable:** `fase4-shader-basico.html` — ShaderMaterial custom con uniforms.

### Semana 5: Shaders Intermedios

| Día | Tema | Actividad | Verificación |
|---|---|---|---|
| 1 | Noise (Simplex, Perlin) | Noise en fragment shader | Visual noise |
| 2 | UV manipulation | Distorsión UV con time uniform | Animación UV |
| 3 | SDF (Signed Distance Fields) | Dibujar formas con SDF | Formas geométricas |
| 4 | Lighting personalizado | Phong desde cero | Lighting visible |
| 5 | Normal mapping | Mapeo de normales con textura | Bump map |
| 6 | Fresnel effect | Efecto Fresnel en shader | Fresnel visible |
| 7 | Composición | Combinar 3 efectos en un shader | Composite demo |

**Entregable:** `fase5-shaders-intermedios.html` — agua procedural + fuego + Fresnel.

### Semana 6: Shaders Avanzados

| Día | Tema | Actividad | Verificación |
|---|---|---|---|
| 1 | Ray marching | Renderizar SDF con ray marching | Esfera SDF |
| 2 | Ray tracing básico | Ray trace simple en fragment shader | Simple reflection |
| 3 | Volumetric rendering | Niebla volumétrica | Volumen visible |
| 4 | Particle systems GPU | Partículas en vertex shader | 100k particles at 60fps |
| 5 | Tessellation simulation | Subdivisión de malla en shader | Smooth tessellation |
| 6 | Compute-like effects | Simulación en fragment shader | Physics sim |
| 7 | Optimización shader | Profiler + optimización | 20% perf gain |

**Entregable:** `fase6-shaders-avanzados.html` — ray marching + partículas GPU.

---

## Fase 3: Performance y Arquitectura (Semanas 7-9)

### Semana 7: Escalabilidad Masiva

| Día | Tema | Actividad | Verificación |
|---|---|---|---|
| 1 | InstancedMesh avanzado | 50k instancias con animación | 60fps con contador |
| 2 | Dynamic batching | Batch geometrías dinámicamente | Memory reduction |
| 3 | LOD y frustum culling | 5 niveles de detalle | Switching visible |
| 4 | Texture compression | KTX2/Basis Universal | Memory reduction |
| 5 | LOD custom | LOD con diferencias reales | Quality metrics |
| 6 | Object pooling | Pool de 10k objetos reutilizables | GC profiler |
| 7 | Memory profiling | Detectar y resolver leaks | Heap snapshot |

**Entregable:** `fase7-escalabilidad.html` — 100k instancias a 60fps.

### Semana 8: Arquitectura de Escenas Complejas

| Día | Tema | Actividad | Verificación |
|---|---|---|---|
| 1 | Scene graph optimization | Reducir nodos de escena | Node count graph |
| 2 | Asset management | Cargar GLTF con progress bar | Loading manager |
| 3 | Scene chunking | Dividir escena en chunks | Lazy loading |
| 4 | Occlusion culling | No renderizar objetos ocultos | Culling visible |
| 5 | Portal rendering | Culling por portales | Portal demo |
| 6 | Hierarchical Z-buffer | Optimizar render order | Z-buffer profiler |
| 7 | Scene serialization | Guardar/cargar estado de escena | JSON export |

**Entregable:** `fase8-arquitectura.html` — asset loading + chunks + occlusion culling.

### Semana 9: Web Workers y Async Rendering

| Día | Tema | Actividad | Verificación |
|---|---|---|---|
| 1 | Geometry generation en worker | Generar terreno en worker | Main thread free |
| 2 | Raycasting en worker | Raycast paralelo | FPS improvement |
| 3 | Animation mixing en worker | Animaciones en worker | Smooth animation |
| 4 | Data textures | Pasar datos GPU via texturas | Texture transfer |
| 5 | Transferable objects | Optimizar worker communication | Zero-copy demo |
| 6 | Multi-threaded rendering | OffscreenCanvas + workers | Multi-core usage |
| 7 | Performance benchmarking | Medir todos los benchmarks | Performance report |

**Entregable:** `fase9-webworkers.html` — worker geometry generation + raycasting paralelo.

---

## Fase 4: Post-Processing y Efectos (Semanas 10-11)

### Semana 10: Post-Processing Pipeline

| Día | Tema | Actividad | Verificación |
|---|---|---|---|
| 1 | EffectComposer setup | Configurar pipeline básico | Composer chain |
| 2 | Render targets | Múltiples pasos de render | RT visualization |
| 3 | Bloom | Bloom selectable | Bloom slider |
| 4 | SSAO | Ambient occlusion | AO visible |
| 5 | FXAA | Anti-aliasing | Before/after compare |
| 6 | Chromatic aberration | Efecto de desplazamiento | RGB split |
| 7 | Vignette | Darkening corners | Vignette slider |

**Entregable:** `fase10-postprocessing.html` — bloom + SSAO + FXAA + vignette.

### Semana 11: Efectos Avanzados

| Día | Tema | Actividad | Verificación |
|---|---|---|---|
| 1 | Depth of field | DOF con enfoque selectivo | Focus distance slider |
| 2 | Motion blur | Blur basado en movimiento | Velocity buffer |
| 3 | Tone mapping | ACES, Reinhard, Filmic | Tone mapping selector |
| 4 | Color grading | LUTs y color correction | LUT loader |
| 5 | Screen-space reflections | SSR para reflejos | Reflection quality toggle |
| 6 | Volumetric lights | Ray marching para luces | Volumetric visible |
| 7 | Custom passes | Pass personalizado | Custom shader pass |

**Entregable:** `fase11-efectos-avanzados.html` — DOF + motion blur + tone mapping.

---

## Fase 5: Integración WebMCP y Agentic Loop (Semana 12)

### Semana 12: WebMCP + Three.js + Agent Loop

| Día | Tema | Actividad | Verificación |
|---|---|---|---|
| 1 | WebMCP tool registration | Registrar herramientas Three.js | 4 tools registered |
| 2 | Canvas capture | Capturar frames a WebMCP | Data transfer |
| 3 | Scene inspection | Inspeccionar escena vía WebMCP | Scene data |
| 4 | Agent control | Agent manipula escena | Control log |
| 5 | Receipts y verificación | Generar receipts de interacción | Receipt verified |
| 6 | Integration testing | E2E test: prompt → render → verify | Test passing |
| 7 | Proyecto final | Integración completa | Full demo |

**Entregable:** `fase12-webmcp-integration.html` + test WebMCP.

---

## Proyecto Final: #internetofagents Topology Visualizer

### Objetivo

Crear un visualizador de topología interactivo que combine todo lo aprendido:

| Característica | Tecnología | Dificultad |
|---|---|---|
| 100k nodes instanciados | InstancedMesh | Alta |
| Navegación 3D orbital | OrbitControls + shaders | Media |
| Raycasting y picking | Raycaster + Web Workers | Alta |
| Bloom y color grading | PostProcessing | Media |
| WebMCP inspection | WebMCP tools + receipts | Élite |
| Export GLTF optimizado | Draco compression | Alta |
| Responsive viewport | CSS flex + Three.js resize | Media |

### Especificaciones técnicas

```
- FPS target: 60fps con 50k+ nodes visibles
- Memoria máxima: 500MB VRAM
- Carga inicial: < 3s (asset loading + compression)
- WebMCP: 6 herramientas registradas, 1 invocación read-only verificada
- PostProcessing: Bloom + SSAO + FXAA + Color grading
```

### Verificación final

```bash
# Tests unitarios
node --test tests/threejs-unitary.test.cjs

# Benchmark de performance
node benchmarks/render-bench.cjs --nodes=50000

# WebMCP integration
node render.cjs --webmcp --url=http://127.0.0.1:58978/

# Linter
npm run lint:threejs
```

---

## Recursos de Aprendizaje

| Tipo | URL | Notas |
|---|---|---|
| Book of Shaders | https://thebookofshaders.com/ | Gratis, interactivo |
| Three.js Examples | https://threejs.org/examples/ | 100+ ejemplos |
| Discover Three.js | https://discoverthreejs.com/ | Libro completo |
| WebGL Insights | https://www.webglinsights.com/ | Libro técnico |
| Spector.js | https://spector.babylonjs.com/ | Debugger de shaders |
| Three.js Journey | https://threejs-journey.com/ | Curso premium |
| Real-Time Rendering | https://www.realtimerendering.com/ | La biblia (libro) |
| WebGL Fundamentals | https://webglfundamentals.org/ | Gratis |

---

## Métricas de Progreso

| Métrica | Baseline | Objetivo |
|---|---|---|
| Render objects | 1,000 | 100,000 |
| FPS consistente | 30 | 60+ |
| Memory usage | 500MB | <500MB |
| Shader effects | 0 | 5+ personalizados |
| WebMCP tools | 4 | 6+ |
| Tests pasados | 18 | 25+ |

---

## Evaluación Final

| Criterio | Peso |
|---|---|
| Calidad visual | 25% |
| Performance | 25% |
| Código limpio | 20% |
| Documentación | 15% |
| Creatividad | 15% |

---

**El objetivo no es aprender Three.js. Es aprender a crear experiencias visuales en la web.**

Three.js es solo la herramienta. Los conceptos de gráficos por computadora son transferibles a cualquier plataforma.

---

*Plan creado para #schoolofhermes y #elearnlatam*
*Ingeniería Electrónica Agéntica con Three.js*
*Versión 1.0 — Octubre 2026*
