"""Exact build evaluation via Path of Building's own calc engine.

Foundation for the Theorycrafter "deep" tree optimiser (Steps 50+). PoB's
calc is ~50k lines of Lua we will never reimplement faithfully — so we run
*PoB itself* headless and read back the real numbers.

How it works (the spike's conclusion):

* lupa's embedded LuaJIT can't load PoB's native modules (lua-utf8.dll
  binds to PoB's own lua51.dll). So we drive PoB's **bundled** runtime
  (`.pob_runtime/runtime/lua51.dll`) directly via ctypes — everything
  binds to one runtime, native modules work, zero extra installs.
* We reuse a single live Lua state across evaluations; each call just
  re-imports the build XML and re-runs the calc (~280 ms).

This is a **local/offline tool only** (Windows DLL runtime). The deployed
app never imports it. Run `scripts/setup_pob.py` first to fetch the
runtime.

    uv run python scripts/pob_eval.py        # smoke test on a generated build
"""

from __future__ import annotations

import base64
import ctypes
import os
import zlib
from pathlib import Path

POB_ROOT = Path(os.environ.get("POB_ROOT", ".pob_runtime")).resolve()

# Stats we read back from PoB's main output (the fitness signal).
_OUTPUT_KEYS: tuple[str, ...] = (
    "Life",
    "EnergyShield",
    "Ward",
    "TotalEHP",
    "Mana",
    "ManaUnreserved",
    "FireResist",
    "ColdResist",
    "LightningResist",
    "ChaosResist",
    "TotalDPS",
    "CombinedDPS",
    "FullDPS",
    "AverageDamage",
    "Str",
    "Dex",
    "Int",
)

_INIT_HARNESS = r"""
arg = { [0] = "HeadlessWrapper.lua" }
package.path = package.path .. ";../runtime/lua/?.lua;../runtime/lua/?/init.lua"
package.cpath = package.cpath .. ";../runtime/?.dll"
dofile("HeadlessWrapper.lua")
return "ok"
"""

# Reads the build XML from POB_EVAL_XML, recalcs, returns "k=v;k=v" (or
# "ERR:<msg>" — wrapped in pcall so one bad candidate can't kill the state).
_EVAL_HARNESS_TMPL = r"""
local ok, err = pcall(function()
  local f = assert(io.open(os.getenv("POB_EVAL_XML"), "r"))
  local xml = f:read("*a"); f:close()
  loadBuildFromXML(xml, "eval")
end)
if not ok then return "ERR:" .. tostring(err) end
local o = build.calcsTab.mainOutput
local keys = {%s}
local parts = {}
for _, k in ipairs(keys) do
  local v = o[k]
  if v ~= nil then parts[#parts+1] = k .. "=" .. tostring(v) end
end
return table.concat(parts, ";")
"""


class PobEvalError(RuntimeError):
    """A candidate build could not be evaluated (PoB raised, or no runtime)."""


def decode_pob_code(code: str) -> str:
    """PoB import code (url-safe base64 + zlib) -> raw XML."""
    padded = code + "=" * (-len(code) % 4)
    return zlib.decompress(base64.urlsafe_b64decode(padded.encode())).decode("utf-8")


class PobEvaluator:
    """Holds a live PoB Lua state; ``evaluate`` returns exact stats.

    NOTE: construction ``chdir``s into the PoB ``src/`` directory (PoB uses
    relative ``dofile``), so use this in a dedicated process.
    """

    def __init__(self, pob_root: Path = POB_ROOT) -> None:
        src = pob_root / "src"
        runtime = pob_root / "runtime"
        if not (src / "HeadlessWrapper.lua").exists():
            raise PobEvalError(
                f"PoB runtime not found at {pob_root}. Run: uv run python scripts/setup_pob.py"
            )
        self._tmp_xml = runtime / ".pob_eval_tmp.xml"
        os.environ["POB_EVAL_XML"] = str(self._tmp_xml)
        os.environ["CI"] = "true"  # skip ModCache (avoids needing Inflate at startup)

        add_dll = getattr(os, "add_dll_directory", None)
        if add_dll is not None:
            add_dll(str(runtime))
        os.environ["PATH"] = str(runtime) + os.pathsep + os.environ.get("PATH", "")
        os.chdir(src)

        lua = ctypes.CDLL(str(runtime / "lua51.dll"))
        vp, ci, cc = ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p
        lua.luaL_newstate.restype = vp
        lua.luaL_openlibs.argtypes = [vp]
        lua.luaL_loadstring.argtypes = [vp, cc]
        lua.luaL_loadstring.restype = ci
        lua.lua_pcall.argtypes = [vp, ci, ci, ci]
        lua.lua_pcall.restype = ci
        lua.lua_tolstring.argtypes = [vp, ci, vp]
        lua.lua_tolstring.restype = cc
        lua.lua_settop.argtypes = [vp, ci]
        self._lua = lua
        self._L = lua.luaL_newstate()
        lua.luaL_openlibs(self._L)

        self._run_chunk(_INIT_HARNESS)
        keys = ",".join(f'"{k}"' for k in _OUTPUT_KEYS)
        self._eval_chunk = (_EVAL_HARNESS_TMPL % keys).encode("utf-8")

    def _run_chunk(self, chunk: str | bytes) -> str:
        lua, lo = self._lua, self._L
        data = chunk.encode("utf-8") if isinstance(chunk, str) else chunk
        lua.lua_settop(lo, 0)
        if lua.luaL_loadstring(lo, data) != 0:
            msg = (lua.lua_tolstring(lo, -1, None) or b"").decode("utf-8", "replace")
            lua.lua_settop(lo, 0)
            raise PobEvalError(f"compile: {msg}")
        if lua.lua_pcall(lo, 0, 1, 0) != 0:
            msg = (lua.lua_tolstring(lo, -1, None) or b"").decode("utf-8", "replace")
            lua.lua_settop(lo, 0)
            raise PobEvalError(f"run: {msg}")
        res = (lua.lua_tolstring(lo, -1, None) or b"").decode("utf-8", "replace")
        lua.lua_settop(lo, 0)
        return res

    def evaluate(self, pob_code: str) -> dict[str, float]:
        """Return PoB-exact stats for a build code. Raises PobEvalError if
        PoB couldn't load/calc the build."""
        self._tmp_xml.write_text(decode_pob_code(pob_code), encoding="utf-8")
        out = self._run_chunk(self._eval_chunk)
        if out.startswith("ERR:"):
            raise PobEvalError(out[4:])
        stats: dict[str, float] = {}
        for pair in out.split(";"):
            if not pair:
                continue
            k, _, v = pair.partition("=")
            try:
                stats[k] = float(v)
            except ValueError:
                continue
        return stats


def _smoke_test() -> int:
    from poe1_fob.theory import TheoryIntent, generate_build

    sk = generate_build(
        TheoryIntent(
            character_class="Marauder",
            ascendancy="Juggernaut",
            primary_skill="Cyclone",
            damage_type="physical",
            defence_archetype="life",
            budget="endgame",
            focus="allcontent",
        )
    )
    ev = PobEvaluator()
    stats = ev.evaluate(sk.pob_code)
    print("=== PoB-exact stats for a generated Marauder/Juggernaut Cyclone ===")
    for k in _OUTPUT_KEYS:
        if k in stats:
            print(f"  {k:16} = {stats[k]:g}")
    return 0 if stats else 1


if __name__ == "__main__":
    raise SystemExit(_smoke_test())
