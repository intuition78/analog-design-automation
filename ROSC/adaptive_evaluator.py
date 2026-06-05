"""adaptive_evaluator.py — N단 ROSC 자율 측정 + 실패 시 안전 복구."""
import time
from set_stages import set_n_stages, get_current_n
from run_sim import run_simulation_and_wait, wait_for_idle
from measure import measure_latest

SESSION = "fnxSession1"
TEST_NAME = "test_jhyang2_SIM_ROSC_1"
SAFE_N = 51   # 실패 시 자동 복구 단 수 (검증된 동작점)

TRAN_INIT = 10e-9         # 첫 시도 (외삽 데이터 없을 때) — 짧게 시작, 부족하면 늘림
TRAN_TARGET_CYCLES = 30   # 목표 주기 수
TRAN_MIN_CYCLES = 30      # ★ 최소 이만큼 주기를 봐야 'good' 인정
TRAN_MARGIN = 1.2         # ★ 계산값에 곱하는 마진 (아슬아슬 29주기 방지)
TRAN_STARTUP_FRAC = 0.4   # tran의 앞 40%는 startup으로 가정 (measure와 일치)
TRAN_STARTUP = 3e-9
TRAN_MIN = 5e-9
TRAN_MAX = 3000e-9        # 큰 N(저주파)도 30주기 담도록 상한 키움
GROW_FACTOR = 3.0         # 발진 안 한 경우의 fallback 증가율
MAX_ATTEMPTS = 4
SIM_TIMEOUT = 600

NO_OSC_SWING = 0.21
MAX_JITTER = 0.15         # 주기 변동계수 이 이상이면 다중모드(깨진 발진) 의심
DUTY_MIN = 0.30          # 정상 ROSC 듀티 하한
DUTY_MAX = 0.70          # 정상 ROSC 듀티 상한
MAX_DUTY_STD = 0.15      # 듀티 표준편차 이 이상이면 불안정


def _set_tran(client, stop_sec):
    s = f'{stop_sec * 1e9:.3f}n'
    r = client.execute_skill(
        f'maeSetAnalysis("{TEST_NAME}" "tran" '
        f'?options `(("stop" "{s}")) ?session "{SESSION}")'
    )
    return r.output and "t" in r.output and not r.errors


class AdaptiveEvaluator:
    def __init__(self, client, vdd=0.7, verbose=True):
        self.c = client
        self.vdd = vdd
        self.verbose = verbose
        self.history = []

    def suggest_tran(self, n_new):
        """첫 tran 추정.
        - 이전 good 데이터 있으면: 가장 가까운 N의 성공 tran을 주파수 비례로 스케일
          (100단→50단이면 주기 절반 → tran 절반, + 마진)
        - 없으면: 짧게 시작 (10ns), 부족하면 재계산이 알아서 늘림."""
        good_hist = [h for h in self.history if h.get("verdict") == "good"]
        if not good_hist:
            return TRAN_INIT
        # 가장 가까운 N의 실측 주기로 새 N의 주기 외삽 (freq ∝ 1/N)
        nearest = min(good_hist, key=lambda h: abs(h["n"] - n_new))
        period_new = (1.0 / nearest["freq"]) * (n_new / nearest["n"])
        return self._tran_for_period(period_new)

    @staticmethod
    def _tran_for_period(period):
        """주기가 period일 때 TRAN_TARGET_CYCLES 주기를 (startup 이후) 담는 tran.
        측정은 뒤 (1-startup_frac) 구간에서만 → 그만큼 키우고 + 마진."""
        usable_frac = 1.0 - TRAN_STARTUP_FRAC
        need = (period * TRAN_TARGET_CYCLES) / usable_frac
        need = need * TRAN_MARGIN + TRAN_STARTUP
        return max(TRAN_MIN, min(TRAN_MAX, need))

    def classify(self, result):
        """주기 수 + 파형 건전성 기반 분류.
        - no_osc      : 거의 교차 없고 swing 작음 → 발진 X
        - degenerate  : 발진은 하나 다중모드/깨진 파형 (jitter↑ 또는 duty 비정상)
                        → 클럭으로 쓸 수 없음. FoM 무효 처리.
        - good        : 깨끗한 단일모드 발진, 충분한 주기 수
        - marginal    : 발진 정상이나 주기 수 부족 → tran 재계산 재시도
        - insufficient: 교차 매우 적음 → 재시도"""
        n_cross = result["n_crossings"]
        n_periods = result.get("n_periods", 0)
        swing = result["clk_swing"]
        jitter = result.get("jitter", 0.0)
        duty = result.get("duty", 0.0)
        duty_std = result.get("duty_std", 0.0)

        if n_cross <= 1 and swing < NO_OSC_SWING:
            return "no_osc"

        # 파형 건전성 체크 — 다중모드/깨진 발진 감지
        # (주기 수가 충분히 잡혔을 때만 신뢰성 있게 판정)
        if n_periods >= 10:
            unhealthy = (jitter >= MAX_JITTER
                         or duty < DUTY_MIN or duty > DUTY_MAX
                         or duty_std >= MAX_DUTY_STD)
            if unhealthy:
                return "degenerate"

        if n_periods >= TRAN_MIN_CYCLES and jitter < MAX_JITTER:
            return "good"
        if n_cross >= 3:
            return "marginal"
        return "insufficient"

    def _recover_safe(self):
        """실패 후 schematic을 안전 N으로 복구."""
        if self.verbose:
            print(f"  ⚠ 실패 — schematic을 N={SAFE_N}으로 복구")
        try:
            set_n_stages(self.c, SAFE_N)
        except Exception as e:
            if self.verbose:
                print(f"     복구 실패: {e}")

    def evaluate(self, n):
        if self.verbose:
            print(f"\n{'='*70}\n  ▶ N = {n} 자율 측정 시작\n{'='*70}")

        # 1. 단 수 변경
        try:
            cur = get_current_n(self.c)
        except Exception as e:
            if self.verbose:
                print(f"  ❌ get_current_n 실패 (모달?): {e}")
            return {"n": n, "verdict": "comm_failed", "n_crossings": 0,
                    "n_periods": 0, "jitter": 0,
                    "clk_swing": 0, "freq": 0, "i_avg": 0, "power": 0,
                    "fom": 0, "oscillating": False}

        if cur != n:
            if self.verbose:
                print(f"  단 수 변경: {cur} → {n}", end="", flush=True)
            t0 = time.time()
            chg = set_n_stages(self.c, n)
            if chg["status"] not in ("ok", "no-change"):
                if self.verbose:
                    print(f"  ❌ {chg['status']}")
                self._recover_safe()
                return {"n": n, "verdict": "set_failed", "n_crossings": 0,
                        "n_periods": 0, "jitter": 0,
                        "clk_swing": 0, "freq": 0, "i_avg": 0, "power": 0,
                        "fom": 0, "oscillating": False}
            if self.verbose:
                print(f"  ({time.time()-t0:.1f}초)")

        # 2. 시도 루프 — 실측 freq로 tran을 적응적으로 재계산
        tran = self.suggest_tran(n)
        last_result = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            if self.verbose:
                src = "외삽" if any(h.get("verdict") == "good" for h in self.history) else "첫 시도"
                print(f"\n  [시도 {attempt}/{MAX_ATTEMPTS}] tran = {tran*1e9:.1f} ns ({src})")

            _set_tran(self.c, tran)
            sim = run_simulation_and_wait(self.c, timeout=SIM_TIMEOUT, verbose=self.verbose)
            if sim["status"] != "ok":
                if self.verbose:
                    print(f"    ❌ 시뮬 실패: {sim.get('msg', sim['status'])}")
                self._recover_safe()
                return {"n": n, "verdict": "sim_failed", "sim": sim,
                        "n_crossings": 0, "n_periods": 0, "jitter": 0,
                        "clk_swing": 0, "freq": 0, "i_avg": 0,
                        "power": 0, "fom": 0, "oscillating": False}

            try:
                m = measure_latest(vdd=self.vdd)
            except Exception as e:
                if self.verbose:
                    print(f"    ❌ 측정 실패: {e}")
                self._recover_safe()
                return {"n": n, "verdict": "measure_failed",
                        "n_crossings": 0, "n_periods": 0, "jitter": 0,
                        "clk_swing": 0, "freq": 0, "i_avg": 0,
                        "power": 0, "fom": 0, "oscillating": False}

            verdict = self.classify(m)
            last_result = {**m, "tran_set": tran, "attempt": attempt, "verdict": verdict, "n": n}

            if self.verbose:
                swing_str = f"swing={m['clk_swing']*1000:.0f}mV"
                if m["oscillating"]:
                    print(f"    측정: freq={m['freq']/1e9:.3f}GHz  "
                          f"I_avg={m['i_avg']*1e6:.1f}µA  "
                          f"periods={m.get('n_periods',0)}  "
                          f"jitter={m.get('jitter',0)*100:.0f}%  "
                          f"duty={m.get('duty',0)*100:.0f}%±{m.get('duty_std',0)*100:.0f}%")
                    print(f"    FoM = {m['fom']:.3e}")
                else:
                    print(f"    측정: 발진 안 함 (crossings={m['n_crossings']}, {swing_str})")
                print(f"    판정: {verdict.upper()}")

            # degenerate: 다중모드/깨진 발진 → FoM 무효화 (옵티마이저가 회피)
            if verdict == "degenerate":
                last_result["fom"] = 0.0
                last_result["oscillating"] = False
                if self.verbose:
                    print(f"    ⚠ 다중모드/깨진 파형 — 클럭 부적합. FoM=0 처리")
                break

            # 확정 케이스
            if verdict in ("good", "no_osc"):
                break

            # 마지막 시도였으면 그대로 마감
            if attempt == MAX_ATTEMPTS:
                last_result["verdict"] = "marginal_final" if verdict == "marginal" else "gave_up"
                break

            # ★ 적응적 tran 재계산
            #   핵심: 방금 본 주기 수(n_periods)와 목표(30)의 비율로 직접 스케일.
            #   "3주기 봤고 30주기 목표면 → tran을 10배" + 마진.
            #   이게 freq를 정확히 모를 때도(부족해도) 작동하는 가장 직접적 비례.
            seen_periods = m.get("n_periods", 0)
            if seen_periods >= 2:
                # 직접 비례: 목표/실측 배율 + 마진
                scale = (TRAN_TARGET_CYCLES / seen_periods) * TRAN_MARGIN
                # startup이 차지한 고정 시간은 비례 대상이 아니므로,
                # 측정 가능 구간만 스케일하는 게 이상적이나, 단순·안전하게 전체 ×scale
                new_tran = min(tran * scale, TRAN_MAX)
                # 최소한 늘어나야 함 (혹시 scale<1이어도 약간은)
                if new_tran <= tran:
                    new_tran = min(tran * 1.5, TRAN_MAX)
                tran = new_tran
                if self.verbose:
                    print(f"    → {seen_periods}주기 관측 → 목표 {TRAN_TARGET_CYCLES}주기 위해 "
                          f"×{scale:.1f} → tran {tran*1e9:.1f} ns")
            else:
                # 거의 발진 안 함 → 큰 배율로
                tran = min(tran * GROW_FACTOR, TRAN_MAX)
                if self.verbose:
                    print(f"    → 주기 거의 없음, tran ×{GROW_FACTOR} = {tran*1e9:.1f} ns")

            wait_for_idle(5.0, verbose=False)
        else:
            last_result["verdict"] = "gave_up"

        self.history.append(last_result)
        if self.verbose:
            v = last_result["verdict"]
            badge = {"good": "✓", "marginal_final": "△", "no_osc": "✗ 발진 X",
                     "gave_up": "⚠ 포기"}.get(v, v)
            print(f"\n  ▶ N={n} 최종: {badge}")
        return last_result


if __name__ == "__main__":
    from vb_connect import get_client
    c = get_client()
    ae = AdaptiveEvaluator(c, vdd=0.7, verbose=True)
    for n in [11, 51, 101]:
        ae.evaluate(n)
