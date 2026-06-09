import os
import re
import time
import glob
import threading
import ctypes

CMD_DIR = os.path.join(os.environ.get("USERPROFILE", ""), "Documents", "Warcraft III", "CustomMapData")
EVAL_OUT = os.path.join(CMD_DIR, "23race_eval_out.pld")
OUT_GLOB = os.path.join(CMD_DIR, "23race_eval_out_[0-9]*.pld")
HB_FILE = os.path.join(CMD_DIR, "23race_eval_hb.pld")
IN_GLOB = os.path.join(CMD_DIR, "23race_eval_[0-9]*.pld")
IN_RE = re.compile(r"23race_eval_(\d+)\.pld$", re.I)

HEX_CHUNK = 200

PLD_TEMPLATE = (
    "function PreloadFiles takes nothing returns nothing\n"
    "\r\n"
    "\tcall PreloadStart()\r\n"
    '\tcall Preload( "")\n'
    "{chunk_calls}"
    'call Preload("" )\r\n'
    "\tcall PreloadEnd( 0.0 )\r\n"
    "\n"
    "endfunction\n\n\r\n"
)


_global_bridge_client = None
_lock = threading.Lock()


def get_bridge_client():
    with _lock:
        return _global_bridge_client


def set_bridge_client(client):
    global _global_bridge_client
    with _lock:
        _global_bridge_client = client


def _out_file(cmd_dir, seq):
    return os.path.join(cmd_dir, "23race_eval_out_%04d.pld" % seq)


def _dechex(hexstr):
    try:
        return bytes.fromhex(hexstr).decode("utf-8", errors="replace")
    except Exception:
        return "<undecodable hex len=%d>" % len(hexstr)


class BridgeClient:

    def __init__(self, cmd_dir=None, postfix=""):
        self._cmd_dir = cmd_dir or CMD_DIR
        self._in_glob = os.path.join(self._cmd_dir, "23race_eval_[0-9]*.pld")
        self._in_re = re.compile(r"23race_eval_(\d+)\.pld$", re.I)
        self._exec_lock = threading.Lock()

    @property
    def cmd_dir(self):
        return self._cmd_dir

    @property
    def is_configured(self):
        return os.path.isdir(self._cmd_dir)

    def is_game_running(self):
        return os.path.isdir(self._cmd_dir) and bool(glob.glob(self._in_glob))

    def _read_hb(self):
        hb_path = os.path.join(self._cmd_dir, "23race_eval_hb.pld")
        try:
            data = open(hb_path, "r", encoding="utf-8", errors="replace").read()
        except OSError:
            return None
        m = re.search(r'Preload\(\s*"hb\|(\d+)"\s*\)', data)
        return int(m.group(1)) if m else None

    def _next_seq(self):
        hb = self._read_hb()
        if hb is not None:
            return hb
        n = 0
        in_glob = os.path.join(self._cmd_dir, "23race_eval_[0-9]*.pld")
        in_re = re.compile(r"23race_eval_(\d+)\.pld$", re.I)
        for p in glob.glob(in_glob):
            m = in_re.search(os.path.basename(p))
            if m:
                n = max(n, int(m.group(1)))
        return n + 1

    def _write_pld(self, seq, hex_code):
        total = max(1, (len(hex_code) + HEX_CHUNK - 1) // HEX_CHUNK)
        calls = []
        for i in range(total):
            chunk = hex_code[i * HEX_CHUNK : (i + 1) * HEX_CHUNK]
            calls.append(
                'call BlzSendSyncData("23RaceEval","eval|%d|%d|%d|%s")\n'
                % (seq, i + 1, total, chunk)
            )
        calls.append("call BlzSetAbilityTooltip('AHbz',\"l%d\",0)\n" % seq)
        blob = PLD_TEMPLATE.format(chunk_calls="".join(calls)).encode("utf-8")
        path = os.path.join(self._cmd_dir, "23race_eval_%04d.pld" % seq)
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(blob)
        os.replace(tmp, path)

    def _parse_out(self, want_seq):
        src = _out_file(self._cmd_dir, want_seq)
        if not os.path.exists(src):
            src = os.path.join(self._cmd_dir, "23race_eval_out.pld")
        if not os.path.exists(src):
            return None
        try:
            data = open(src, "r", encoding="utf-8", errors="replace").read()
        except OSError:
            return None
        chunks, ok, total, legacy = {}, None, None, None
        for line in re.findall(r'Preload\(\s*"(.*?)"\s*\)', data):
            f = line.split("|")
            if len(f) < 3 or f[0] != str(want_seq):
                continue
            if len(f) >= 5 and f[2].isdigit() and f[3].isdigit():
                ok = f[1] == "1"
                total = int(f[3])
                chunks[int(f[2])] = f[4]
            elif len(f) == 3:
                legacy = (want_seq, f[1] == "1", f[2])
        if total is not None and len(chunks) >= total:
            return want_seq, ok, _dechex("".join(chunks.get(i, "") for i in range(1, total + 1)))
        if legacy is not None:
            return legacy[0], legacy[1], _dechex(legacy[2])
        return None

    def _wait_for_file(self, filepath, deadline):
        if os.path.exists(filepath):
            return True
        dirpath = os.path.dirname(filepath)
        filename = os.path.basename(filepath)
        kernel32 = ctypes.windll.kernel32
        hDir = kernel32.CreateFileW(
            dirpath, 0x0001, 0x0007, None, 3, 0x02000000, None)
        if hDir == -1:
            while time.time() < deadline:
                if os.path.exists(filepath):
                    return True
                time.sleep(0.05)
            return False
        try:
            buf = ctypes.create_string_buffer(4096)
            bytes_returned = ctypes.c_ulong(0)
            need = filename.encode("utf-16-le")
            while True:
                remaining_ms = int((deadline - time.time()) * 1000)
                if remaining_ms <= 0:
                    break
                wait = min(remaining_ms, 500)
                ok = kernel32.ReadDirectoryChangesW(
                    hDir, buf, len(buf), False, 0x00000001,
                    ctypes.byref(bytes_returned), None, None)
                if ok and bytes_returned.value > 0:
                    if need in buf.raw[:bytes_returned.value]:
                        time.sleep(0.05)
                        return True
                if os.path.exists(filepath):
                    return True
        finally:
            kernel32.CloseHandle(hDir)
        return os.path.exists(filepath)

    def reset(self):
        out_glob = os.path.join(self._cmd_dir, "23race_eval_out_[0-9]*.pld")
        hb_path = os.path.join(self._cmd_dir, "23race_eval_hb.pld")
        eval_out = os.path.join(self._cmd_dir, "23race_eval_out.pld")
        in_glob = os.path.join(self._cmd_dir, "23race_eval_[0-9]*.pld")
        removed = 0
        for p in glob.glob(in_glob) + glob.glob(out_glob) + [eval_out, hb_path]:
            try:
                os.remove(p)
                removed += 1
            except OSError:
                pass
        return removed

    def ping(self, timeout=8.0):
        ok, result = self.exec_lua("return 'pong'", timeout=timeout)
        return ok and "pong" in result.lower()

    def exec_lua(self, code, timeout=8.0, retries=0):
        with self._exec_lock:
            last_result = (False, "")
            for attempt in range(retries + 1):
                ok, val = self._exec_lua_locked(code, timeout)
                if ok:
                    return ok, val
                last_result = (ok, val)
                if attempt < retries:
                    time.sleep(0.5)
            return last_result

    def _exec_lua_locked(self, code, timeout):
        seq = self._next_seq()
        out_file = _out_file(self._cmd_dir, seq)
        eval_out = os.path.join(self._cmd_dir, "23race_eval_out.pld")
        for stale in (out_file, eval_out):
            try:
                os.remove(stale)
            except OSError:
                pass
        hx = code.encode("utf-8").hex()
        self._write_pld(seq, hx)
        deadline = time.time() + timeout
        if self._wait_for_file(out_file, deadline):
            r = self._parse_out(seq)
            if r and r[0] == seq:
                _, ok, val = r
                return ok, val
        return False, "TIMEOUT: no result for seq=%d within %ss" % (seq, timeout)
