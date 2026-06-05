"""measure.py — ROSC 시뮬 결과 측정 (CLK swing 추가)."""
import os, re, subprocess
from pathlib import Path
import numpy as np

SIM_BASE = Path("/user/adtco/USER/j27.yang/j27.yang+ss_isen1_sf2pp_5108202+MPW11+3/"
                "simulation/test_jhyang2/SIM_ROSC/maestro/results/maestro")
PSF_TOOL = "/appl/LINUX/opus514/tools/dfII/bin/psf"
LIB_DIR  = Path("/user/adtco/USER/j27.yang/Bridge/_libs")
PSF_ASCII = Path("/user/adtco/USER/j27.yang/Bridge/_tran_ascii.psf")
DEFAULT_VDD = 0.7


def find_latest_history(base: Path = SIM_BASE) -> Path | None:
    candidates = []
    for done in base.rglob(".simDone"):
        s = str(done)
        if "_deleted" in s:
            continue
        try:
            hist = done.parents[3]
            tran = done.parent / "tran.tran.tran"
            if tran.exists():
                candidates.append((tran.stat().st_mtime, hist))
        except Exception:
            pass
    if not candidates:
        return None
    return max(candidates, key=lambda x: x[0])[1]


def find_tran_psf(history_dir: Path) -> Path | None:
    matches = list(history_dir.rglob("tran.tran.tran"))
    return matches[0] if matches else None


def psf_bin_to_ascii(psf_bin: Path, out_path: Path = PSF_ASCII) -> Path:
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = str(LIB_DIR) + ":" + env.get("LD_LIBRARY_PATH", "")
    if out_path.exists():
        out_path.unlink()
    r = subprocess.run(
        [PSF_TOOL, "-i", str(psf_bin), "-o", str(out_path)],
        capture_output=True, text=True, env=env, timeout=180,
    )
    if r.returncode != 0 or not out_path.exists():
        raise RuntimeError(f"psf 변환 실패 (rc={r.returncode}): {r.stderr[:300]}")
    return out_path


def parse_psf_value(psf_ascii: Path):
    text = psf_ascii.read_text()
    m_trace = re.search(r'\nTRACE\n(.*?)\n(?:VALUE|END)\n', text, re.DOTALL)
    if not m_trace:
        raise RuntimeError("TRACE 섹션 못 찾음")
    trace_body = m_trace.group(1)
    m_grp = re.search(r'"group"\s+GROUP\s+(\d+)\n(.*)', trace_body, re.DOTALL)
    if not m_grp:
        raise RuntimeError("group 정의 못 찾음")
    n_sig = int(m_grp.group(1))
    sig_lines = m_grp.group(2).strip().splitlines()
    signals = []
    for line in sig_lines[:n_sig]:
        m = re.match(r'"([^"]+)"\s+"([^"]+)"', line.strip())
        if m:
            signals.append(m.group(1))
    if len(signals) != n_sig:
        raise RuntimeError(f"신호 이름 파싱 실패: {len(signals)} / {n_sig}")

    iv = text.find("\nVALUE\n")
    body = text[iv + len("\nVALUE\n"):]
    m_end = re.search(r"\nEND\b", body)
    if m_end:
        body = body[:m_end.start()]
    nums = re.findall(r'-?\d+\.\d+e?[+-]?\d*|-?\d+\.\d+|-?\d+e?[+-]?\d*', body)
    period = 1 + n_sig
    n_time = len(nums) // period
    arr = np.array([float(x) for x in nums[:n_time * period]]).reshape(n_time, period)
    return arr[:, 0], arr[:, 1:], signals


def calc_freq(t, clk, vdd, startup_frac=0.3):
    """VDD/2 교차로 주파수 + 파형 건전성 측정.
    Returns: (freq, n_crossings, n_periods, jitter, duty, duty_std)
      jitter   : 상향교차 주기의 변동계수. 단일모드면 작음(~5%), 다중모드면 큼.
      duty     : 평균 듀티비 (high 시간 / 주기). 정상 ROSC면 ~0.5.
      duty_std : 듀티비의 표준편차. 다중모드면 들쭉날쭉해서 큼."""
    start = int(len(t) * startup_frac)
    tt, cc = t[start:], clk[start:]
    th = vdd / 2.0

    # 상향/하향 교차 모두
    up = np.where((cc[:-1] < th) & (cc[1:] >= th))[0]
    dn = np.where((cc[:-1] >= th) & (cc[1:] < th))[0]
    if len(up) < 3:
        return 0.0, len(up), 0, 0.0, 0.0, 0.0

    def interp(idx):
        return np.array([tt[i] + (th - cc[i]) * (tt[i+1]-tt[i]) / (cc[i+1]-cc[i]) for i in idx])
    up_t = interp(up)
    dn_t = interp(dn)

    periods = np.diff(up_t)
    mean_period = periods.mean()
    jitter = float(periods.std() / mean_period) if mean_period > 0 else 0.0
    freq = 1.0 / mean_period

    # duty: 각 상향교차 후 다음 하향교차까지 = high 구간
    duties = []
    for i in range(len(up_t) - 1):
        # up_t[i] 이후 첫 하향교차
        nxt_dn = dn_t[dn_t > up_t[i]]
        if len(nxt_dn) > 0:
            high_time = nxt_dn[0] - up_t[i]
            this_period = up_t[i+1] - up_t[i]
            if this_period > 0:
                duties.append(high_time / this_period)
    if duties:
        duties = np.array(duties)
        duty = float(duties.mean())
        duty_std = float(duties.std())
    else:
        duty, duty_std = 0.0, 0.0

    return freq, len(up), len(periods), jitter, duty, duty_std


def calc_i_avg(t, current, startup_frac=0.3):
    start = int(len(t) * startup_frac)
    return abs(float(current[start:].mean()))


def calc_clk_swing(t, clk, startup_frac=0.3):
    """CLK 신호의 진폭 (max - min). 발진 여부 판정용."""
    start = int(len(t) * startup_frac)
    seg = clk[start:]
    return float(seg.max() - seg.min())


def measure_latest(vdd=DEFAULT_VDD, clk_signal="CLK", current_signal="V0:p") -> dict:
    hist = find_latest_history()
    if hist is None:
        raise RuntimeError("유효한 history 없음")
    psf_bin = find_tran_psf(hist)
    if psf_bin is None:
        raise RuntimeError(f"tran.tran.tran 없음: {hist}")

    psf_ascii = psf_bin_to_ascii(psf_bin)
    t, data, signals = parse_psf_value(psf_ascii)
    if clk_signal not in signals or current_signal not in signals:
        raise RuntimeError(f"신호 부족: signals[:10]={signals[:10]}")

    clk = data[:, signals.index(clk_signal)]
    cur = data[:, signals.index(current_signal)]
    freq, n_cross, n_periods, jitter, duty, duty_std = calc_freq(t, clk, vdd)
    i_avg = calc_i_avg(t, cur)
    swing = calc_clk_swing(t, clk)
    power = i_avg * vdd
    fom = freq / power if (freq > 0 and power > 0) else 0.0

    return {
        "history_dir": str(hist),
        "freq": freq,
        "i_avg": i_avg,
        "power": power,
        "fom": fom,
        "n_crossings": n_cross,
        "n_periods": n_periods,
        "jitter": jitter,
        "duty": duty,
        "duty_std": duty_std,
        "clk_swing": swing,
        "n_time_points": len(t),
        "oscillating": freq > 0,
        "tran_stop": float(t[-1]),
    }


if __name__ == "__main__":
    r = measure_latest()
    print(f"history: {r['history_dir']}")
    print(f"tran   : {r['tran_stop']*1e9:.2f} ns ({r['n_time_points']} 점)")
    print(f"swing  : {r['clk_swing']*1000:.1f} mV   crossings: {r['n_crossings']}  "
          f"periods: {r['n_periods']}")
    print(f"jitter : {r['jitter']*100:.1f}%   duty: {r['duty']*100:.1f}%  "
          f"duty_std: {r['duty_std']*100:.1f}%")
    if r["oscillating"]:
        print(f"freq   : {r['freq']/1e9:.4f} GHz")
        print(f"I_avg  : {r['i_avg']*1e6:.4f} uA")
        print(f"FoM    : {r['fom']:.4e}")
