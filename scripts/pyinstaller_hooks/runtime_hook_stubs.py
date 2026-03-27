"""PyInstaller runtime hook: inject lightweight stubs for numba and scipy.

mlx_whisper.timing imports numba and scipy at module level for word-level
timestamp alignment (DTW + median filter).  Talky never enables word_timestamps
so these functions are never called.  Providing thin stubs avoids bundling
~150 MB of unused native code (numba + llvmlite + scipy).
"""

import sys
import types


def _make_numba_stub():
    numba = types.ModuleType("numba")

    def jit(*args, **kwargs):
        if args and callable(args[0]):
            return args[0]

        def decorator(fn):
            return fn

        return decorator

    numba.jit = jit
    return numba


def _make_scipy_stub():
    scipy = types.ModuleType("scipy")
    signal = types.ModuleType("scipy.signal")

    def medfilt(volume, kernel_size=None):
        return volume

    signal.medfilt = medfilt
    scipy.signal = signal
    return scipy, signal


numba = _make_numba_stub()
scipy, scipy_signal = _make_scipy_stub()

sys.modules["numba"] = numba
sys.modules["scipy"] = scipy
sys.modules["scipy.signal"] = scipy_signal
