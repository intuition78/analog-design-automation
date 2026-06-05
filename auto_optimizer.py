"""auto_optimizer.py — N단 ROSC FoM 자율 최적화.

알고리즘:
  Phase 1: Binary search로 발진 가능 최소 N 발견
  Phase 2: Ternary search로 FoM 피크 발견 (캐시 진전 없음 감지로 종료)

끝나면 schematic을 찾은 최적 N으로 적용 (복구 X).
"""
import time
from vb_connect import get_client
from adaptive_evaluator import AdaptiveEvaluator
from set_stages import set_n_stages


def _to_odd(n: int, lo: int = 1, hi: int = 999) -> int:
    n = max(lo, min(hi, n))
    if n % 2 == 0:
        n += 1
    return n


class AutoOptimizer:
    def __init__(self, client, vdd: float = 0.7, verbose: bool = True):
        self.c = client
        self.vdd = vdd
        self.verbose = verbose
        self.ae = AdaptiveEvaluator(client, vdd=vdd, verbose=False)
        self.cache = {}
        self.eval_count = 0

    def _evaluate(self, n: int) -> dict:
        n = _to_odd(n)
        if n in self.cache:
            if self.verbose:
                print(f"    📋 N={n}: 캐시 ({self._fom_str(self.cache[n])})")
            return self.cache[n]
        self.eval_count += 1
        if self.verbose:
            print(f"\n  ┌─ [평가 #{self.eval_count}] N = {n}")
        t0 = time.time()
        r = self.ae.evaluate(n)
        elapsed = time.time() - t0
        self.cache[n] = r
        if self.verbose:
            print(f"  └─ {self._fom_str(r)}  ({elapsed:.0f}초)")
        return r

    @staticmethod
    def _fom_str(r: dict) -> str:
        v = r.get("verdict", "?")
        if v in ("good", "marginal_final"):
            return (f"freq={r['freq']/1e9:.2f}GHz  I={r['i_avg']*1e6:.0f}µA  "
                    f"FoM={r['fom']:.2e}")
        return f"{v.upper()}"

    @staticmethod
    def _is_osc(r: dict) -> bool:
        return r.get("verdict") in ("good", "marginal_final") and r.get("freq", 0) > 0

    def find_oscillation_boundary(self, lo: int, hi: int) -> int:
        if self.verbose:
            print(f"\n{'─'*70}\nPhase 1 — 발진 경계 탐색 (binary search) [{lo}, {hi}]\n{'─'*70}")

        r_hi = self._evaluate(hi)
        if not self._is_osc(r_hi):
            if self.verbose:
                print(f"\n  ⚠ N={hi}에서도 발진 안 함")
            return None

        r_lo = self._evaluate(lo)
        if self._is_osc(r_lo):
            if self.verbose:
                print(f"\n  ✓ N={lo}에서도 발진. 경계는 {lo}")
            return lo

        a, b = lo, hi
        while b - a > 2:
            mid = _to_odd((a + b) // 2)
            if mid == a or mid == b:
                break
            r = self._evaluate(mid)
            if self._is_osc(r):
                b = mid
            else:
                a = mid

        if self.verbose:
            print(f"\n  ✓ 발진 경계 = {b}")
        return b

    def find_fom_peak(self, lo: int, hi: int, tol: int = 3) -> int:
        if self.verbose:
            print(f"\n{'─'*70}\nPhase 2 — FoM 피크 탐색 (ternary search) [{lo}, {hi}]\n{'─'*70}")

        a, b = lo, hi
        prev_m1, prev_m2 = -1, -1   # ★ 무한루프 방지
        max_iters = 20              # ★ 안전망
        for _ in range(max_iters):
            if b - a <= tol:
                break
            m1 = _to_odd(a + (b - a) // 3)
            m2 = _to_odd(b - (b - a) // 3)
            if m1 >= m2:
                break
            # ★ 진전 없음 (직전과 같은 m1, m2) → 종료
            if m1 == prev_m1 and m2 == prev_m2:
                if self.verbose:
                    print(f"\n  (m1/m2가 직전과 같음 — 진전 없음, 후보군 비교로 마무리)")
                break
            prev_m1, prev_m2 = m1, m2

            r1 = self._evaluate(m1)
            r2 = self._evaluate(m2)
            f1 = r1.get("fom", 0)
            f2 = r2.get("fom", 0)
            if self.verbose:
                print(f"\n  비교: N={m1} (FoM={f1:.2e}) vs N={m2} (FoM={f2:.2e})")
            if f1 < f2:
                a = m1
                if self.verbose:
                    print(f"  → 왼쪽 버림. 새 범위 [{a}, {b}]")
            else:
                b = m2
                if self.verbose:
                    print(f"  → 오른쪽 버림. 새 범위 [{a}, {b}]")

        candidates = list(range(a if a % 2 == 1 else a + 1, b + 1, 2))
        if self.verbose:
            print(f"\n  최종 후보군 {candidates} 비교:")
        for n in candidates:
            self._evaluate(n)
        best_n = max(candidates, key=lambda n: self.cache.get(n, {}).get("fom", 0))
        return best_n

    def optimize(self, lo: int = 3, hi: int = 255) -> dict:
        t_start = time.time()
        print("=" * 70)
        print(f"  AutoOptimizer — FoM = freq/(I_avg×VDD) 극대화")
        print(f"  탐색 범위: [{lo}, {hi}]  (홀수만 평가)")
        print("=" * 70)

        boundary = self.find_oscillation_boundary(lo, hi)
        if boundary is None:
            print("\n❌ 전체 범위에서 발진 안 함.")
            return None

        best_n = self.find_fom_peak(boundary, hi)
        best = self.cache[best_n]

        print("\n" + "=" * 70)
        print(f"  최종 결과 (총 {self.eval_count}회 평가, {(time.time()-t_start)/60:.1f}분)")
        print("=" * 70)
        print(f"\n  🏆 최적: N = {best_n}")
        print(f"      freq  = {best['freq']/1e9:.4f} GHz")
        print(f"      I_avg = {best['i_avg']*1e6:.3f} µA")
        print(f"      Power = {best['power']*1e6:.3f} µW")
        print(f"      FoM   = {best['fom']:.4e} Hz/W")

        print(f"\n  평가 이력 (N 오름차순):")
        print(f"  {'N':>4}  {'verdict':<10}  {'freq(GHz)':>10}  {'I_avg(µA)':>10}  {'FoM':>11}")
        print("  " + "─" * 56)
        for n in sorted(self.cache):
            r = self.cache[n]
            v = r.get("verdict", "?")
            if self._is_osc(r):
                star = " ★" if n == best_n else ""
                print(f"  {n:>4}  {v:<10}  {r['freq']/1e9:>10.4f}  "
                      f"{r['i_avg']*1e6:>10.2f}  {r['fom']:>11.3e}{star}")
            else:
                print(f"  {n:>4}  {v:<10}  (발진 X)")

        # ★ 최적값을 schematic에 적용 (복구 X)
        print(f"\n  [적용] schematic을 최적값 N={best_n}으로 설정")
        set_n_stages(self.c, best_n)
        return best


if __name__ == "__main__":
    c = get_client()
    opt = AutoOptimizer(c, vdd=0.7, verbose=True)
    best = opt.optimize(lo=3, hi=255)
