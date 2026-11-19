"""Force the discrete GPU for OpenGL via NVIDIA's own driver-settings API.

nvapi64.dll exports only NvAPI_QueryInterface (ordinal 0x0150E828 is the
undocumented but stable entry). Every other function is resolved by its
32-bit function ID. This is the same layer NVIDIA Control Panel writes to,
so it governs OpenGL — unlike the DirectX UserGpuPreferences registry key.

Target setting: SHIM_MCCOMPAT_ID (0x10810001), value SHIM_MCCOMPAT_ENABLE (1)
= "High-performance NVIDIA processor" for the named application.

    python nv_gpu_select.py --exe "C:/gpu/Scripts/python.exe"
    python nv_gpu_select.py --check
"""
from __future__ import annotations

import argparse
import ctypes as C
import subprocess
import sys
from ctypes import wintypes

# function IDs (stable across driver versions; from nvapi.h)
ID = {
    'Initialize':            0x0150E828,
    'Uninitialize':          0xD22BDD7E,
    'DRS_CreateSession':     0x0694D52E,
    'DRS_DestroySession':    0xDAD9CFF8,
    'DRS_LoadSettings':      0x375DBD6B,
    'DRS_SaveSettings':      0xFCBC7E14,
    'DRS_FindApplicationByName': 0xEEE566B2,
    'DRS_CreateApplication': 0x4347A9DE,
    'DRS_SetSetting':        0x577DD202,
    'DRS_GetSetting':        0x73BF8338,
    'GetErrorMessage':       0x6C2D048C,
}
SHIM_MCCOMPAT_ID = 0x10810001
SHIM_MCCOMPAT_ENABLE = 0x00000001     # high-performance NVIDIA processor
SHIM_MCCOMPAT_AUTO = 0x00000000

NVDRS_SETTING_MAX = 4096


class NVDRS_APPLICATION(C.Structure):
    _fields_ = [('version', C.c_uint32), ('isPredefined', C.c_uint32),
                ('appName', C.c_wchar * 2048), ('userFriendlyName', C.c_wchar * 2048),
                ('launcher', C.c_wchar * 2048), ('fileInFolder', C.c_wchar * 2048),
                ('isMetro', C.c_uint32), ('isCommandLine', C.c_uint32)]


class NVDRS_SETTING_VALUE(C.Union):
    _fields_ = [('u32Value', C.c_uint32), ('wszValue', C.c_wchar * 2048),
                ('binaryValue', C.c_ubyte * 4096)]


class NVDRS_SETTING(C.Structure):
    _fields_ = [('version', C.c_uint32), ('settingName', C.c_wchar * 2048),
                ('settingId', C.c_uint32), ('settingType', C.c_uint32),
                ('settingLocation', C.c_uint32), ('isCurrentPredefined', C.c_uint32),
                ('isPredefinedValid', C.c_uint32),
                ('predefinedValue', NVDRS_SETTING_VALUE),
                ('currentValue', NVDRS_SETTING_VALUE)]


def ver(struct_cls, base_ver):
    return base_ver | C.sizeof(struct_cls)


class NV:
    def __init__(self):
        self.dll = C.CDLL('nvapi64.dll')
        qi = None
        # the export is name-mangled; find it by ordinal-free lookup
        for name in ('nvapi_QueryInterface', 'NvAPI_QueryInterface', '_nvapi_QueryInterface'):
            try:
                qi = getattr(self.dll, name)
                break
            except AttributeError:
                continue
        if qi is None:
            raise RuntimeError('nvapi_QueryInterface export not found')
        qi.restype = C.c_void_p
        qi.argtypes = [C.c_uint32]
        self.qi = qi
        self.fns = {}

    def fn(self, name, restype, argtypes):
        if name not in self.fns:
            addr = self.qi(ID[name])
            if not addr:
                raise RuntimeError(f'function {name} (0x{ID[name]:08X}) not resolved')
            self.fns[name] = C.WINFUNCTYPE(restype, *argtypes)(addr)
        return self.fns[name]

    def init(self):
        f = self.fn('Initialize', C.c_int, [])
        return f()


def check():
    code = ("import mujoco,ctypes;c=mujoco.GLContext(64,64);c.make_current();"
            "g=ctypes.windll.opengl32.glGetString;g.restype=ctypes.c_char_p;"
            "v=g(0x1F01);print(v.decode() if v else 'NULL')")
    p = subprocess.run([sys.executable, '-c', code], capture_output=True,
                       text=True, encoding='utf-8', timeout=120)
    return (p.stdout or p.stderr or '').strip().splitlines()[-1]


def select(exe):
    print(f'  before: {check()}')
    try:
        nv = NV()
    except Exception as exc:
        return {'ok': False, 'reason': f'nvapi unavailable: {exc}'}
    rc = nv.init()
    if rc != 0:
        return {'ok': False, 'reason': f'NvAPI_Initialize rc={rc}'}
    sess = C.c_void_p()
    rc = nv.fn('DRS_CreateSession', C.c_int, [C.POINTER(C.c_void_p)])(C.byref(sess))
    if rc != 0:
        return {'ok': False, 'reason': f'CreateSession rc={rc}'}
    rc = nv.fn('DRS_LoadSettings', C.c_int, [C.c_void_p])(sess)
    if rc != 0:
        return {'ok': False, 'reason': f'LoadSettings rc={rc}'}

    app = NVDRS_APPLICATION()
    # NVDRS_APPLICATION_VER_V4 = sizeof | (4 << 16). The struct carries isMetro
    # (V3) and isCommandLine (V4); tagging it V2 returns rc=-9
    # NVAPI_INCOMPATIBLE_STRUCT_VERSION.
    app.version = ver(NVDRS_APPLICATION, 0x40000)
    app.appName = exe.replace('/', '\\')
    app.userFriendlyName = 'ae-mujoco-render'
    app.launcher = ''
    app.isPredefined = 0
    hprofile = C.c_void_p()
    rc = nv.fn('DRS_FindApplicationByName', C.c_int,
               [C.c_void_p, C.c_wchar_p, C.POINTER(C.c_void_p),
                C.POINTER(NVDRS_APPLICATION)])(sess, app.appName,
                                              C.byref(hprofile), C.byref(app))
    if rc != 0:
        rc = nv.fn('DRS_CreateApplication', C.c_int,
                   [C.c_void_p, C.POINTER(NVDRS_APPLICATION)])(sess, C.byref(app))
        if rc != 0:
            return {'ok': False, 'reason': f'CreateApplication rc={rc}'}
        rc = nv.fn('DRS_FindApplicationByName', C.c_int,
                   [C.c_void_p, C.c_wchar_p, C.POINTER(C.c_void_p),
                    C.POINTER(NVDRS_APPLICATION)])(sess, app.appName,
                                                  C.byref(hprofile), C.byref(app))
        if rc != 0:
            return {'ok': False, 'reason': f'FindApplication after create rc={rc}'}

    st = NVDRS_SETTING()
    st.version = ver(NVDRS_SETTING, 0x10000)
    st.settingId = SHIM_MCCOMPAT_ID
    st.settingType = 0          # DWORD
    st.currentValue.u32Value = SHIM_MCCOMPAT_ENABLE
    rc = nv.fn('DRS_SetSetting', C.c_int,
               [C.c_void_p, C.c_void_p, C.POINTER(NVDRS_SETTING), C.c_uint32,
                C.c_uint32])(sess, hprofile, C.byref(st), 0, 0)
    if rc != 0:
        return {'ok': False, 'reason': f'SetSetting rc={rc}'}
    rc = nv.fn('DRS_SaveSettings', C.c_int, [C.c_void_p])(sess)
    nv.fn('DRS_DestroySession', C.c_int, [C.c_void_p])(sess)
    if rc != 0:
        return {'ok': False, 'reason': f'SaveSettings rc={rc}'}
    after = check()
    return {'ok': True, 'exe': exe, 'after': after,
            'on_nvidia': 'NVIDIA' in after or 'RTX' in after}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--exe', default=sys.executable)
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    if a.check:
        print('  GL_RENDERER:', check())
        return
    r = select(a.exe)
    print(' ', r)
    if r.get('ok') and not r.get('on_nvidia'):
        print('  setting written but adapter unchanged — driver may need a new session')


if __name__ == '__main__':
    main()
