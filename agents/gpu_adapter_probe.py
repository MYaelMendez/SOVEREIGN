"""Find a path to the discrete GPU for MuJoCo's offscreen GL context.

Measured problem: GL_RENDERER = Intel(R) UHD Graphics. The RTX 3050 has never
rasterised a frame; it only runs NVENC at the end. On an Optimus laptop the
default WGL context lands on the integrated adapter.

Candidate levers, tested in order of invasiveness (least first):
  1. MUJOCO_GL=egl        — EGL can enumerate devices, incl. NVIDIA
  2. MUJOCO_GL=glfw       — default; baseline
  3. WGL_NV_gpu_affinity  — enumerate GPUs, build a DC on the NVIDIA one
  4. per-app driver preference (registry / control panel)

Reports the GL_RENDERER each path actually yields. No claims without a string.
"""
import ctypes
import os
import subprocess
import sys
from ctypes import wintypes

PY = sys.executable


def renderer_via_env(backend):
    code = (
        "import mujoco,ctypes;"
        "c=mujoco.GLContext(64,64);c.make_current();"
        "g=ctypes.windll.opengl32.glGetString;g.restype=ctypes.c_char_p;"
        "v=g(0x1F01);print(v.decode() if v else 'NULL')"
    )
    e = dict(os.environ)
    e['MUJOCO_GL'] = backend
    e.pop('PYOPENGL_PLATFORM', None)
    try:
        p = subprocess.run([PY, '-c', code], capture_output=True, text=True,
                           encoding='utf-8', timeout=120, env=e)
        out = (p.stdout or '').strip().splitlines()
        return out[-1] if out else f'FAILED: {(p.stderr or "")[-160:]}'
    except Exception as exc:
        return f'{type(exc).__name__}: {exc}'


def wgl_affinity():
    """WGL_NV_gpu_affinity needs wglGetProcAddress, not a direct export."""
    import mujoco
    ctx = mujoco.GLContext(64, 64)
    ctx.make_current()
    wgl = ctypes.windll.opengl32
    gpa = wgl.wglGetProcAddress
    gpa.restype = ctypes.c_void_p
    gpa.argtypes = [wintypes.LPCSTR]

    hdc = wgl.wglGetCurrentDC()
    proto = ctypes.WINFUNCTYPE(ctypes.c_char_p, wintypes.HDC)
    addr = gpa(b'wglGetExtensionsStringARB')
    if not addr:
        return {'available': False, 'reason': 'wglGetExtensionsStringARB not exposed'}
    get_ext = proto(addr)
    exts = (get_ext(hdc) or b'').decode()
    has = 'WGL_NV_gpu_affinity' in exts
    res = {'available': has, 'extensions_sample': exts[:200]}
    if not has:
        res['reason'] = 'WGL_NV_gpu_affinity absent from this driver/context'
        return res

    # enumerate affinity GPUs
    ENUM = ctypes.WINFUNCTYPE(wintypes.HANDLE, wintypes.HDC, ctypes.c_uint)
    ea = gpa(b'wglEnumGpusFromAffinityDC') or gpa(b'wglEnumGpusNV')
    if not ea:
        res['reason'] = 'no enum entry point'
        return res
    enum = ENUM(ea)
    GPUs = []
    NAME = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HANDLE,
                              ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint))
    na = gpa(b'wglGetGpuNameStringNV')
    for i in range(8):
        h = enum(hdc, i) if ea == gpa(b'wglEnumGpusFromAffinityDC') else enum(i)
        if not h:
            break
        name = b''
        if na:
            buf = ctypes.create_string_buffer(256)
            n = ctypes.c_uint(256)
            if NAME(na)(h, buf, ctypes.byref(n)):
                name = buf.value
        GPUs.append(name.decode(errors='replace'))
    res['gpus'] = GPUs
    return res


def main():
    print('  MuJoCo offscreen GL — which adapter does each backend yield?\n')
    for b in ('glfw', 'egl', 'osmesa'):
        print(f'  MUJOCO_GL={b:8s} -> {renderer_via_env(b)}')
    print()
    try:
        r = wgl_affinity()
        print('  WGL_NV_gpu_affinity:', r)
    except Exception as exc:
        print(f'  WGL_NV_gpu_affinity probe failed: {type(exc).__name__}: {exc}')


if __name__ == '__main__':
    main()
