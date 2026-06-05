"""run_sim.py — sevRun + ADE 완전 idle 감지 (적응형, 시간 하드코딩 X).

★ 완료 판정 = ADE Explorer의 결과 파일들이 일정 시간 안정 (mtime/size 변화 없음)
   관찰 파일:
     - <RUN>.log    (84B → 330B 점프 시 ADE가 완료 인식)
     - <RUN>.rdb    (ADE 결과 DB)
     - <RUN>.msg.db (메시지 DB)
     - tran.tran.tran (Spectre PSF)

★ 적응형:
   - 시뮬 시간 무관 (1초든 5분이든)
   - 회로 종류 무관 (인버터든 OTA든)
   - 발진 안 함 / 사이즈 작은 회로도 OK
"""
import time
from pathlib import Path

SIM_BASE = Path("/user/adtco/USER/j27.yang/j27.yang+ss_isen1_sf2pp_5108202+MPW11+3/"
                "simulation/test_jhyang2/SIM_ROSC/maestro/results/maestro")

# ADE idle 판정: N초 연속 mtime/size 변화 없으면 idle
IDLE_STABILITY = 10.0     # 초


def _capture_state() -> dict:
    """살아있는(=_deleted 제외) 모든 ExplorerR(O)Run 관련 파일의 (size, mtime) 캡처.
    상태 비교용 dict 반환."""
    state = {}
    # ExplorerR(O)Run.*.log, .rdb, .msg.db (ADE 결과 파일들)
    for p in SIM_BASE.glob("ExplorerR*Run*"):
        if "_deleted" in p.name:
            continue
        if p.is_file():
            try:
                st = p.stat()
                state[str(p)] = (st.st_size, st.st_mtime)
            except OSError:
                pass
    # tran.tran.tran (Spectre PSF) — RO 또는 Run 폴더 안
    for tran in SIM_BASE.rglob("tran.tran.tran"):
        if "_deleted" in str(tran):
            continue
        try:
            st = tran.stat()
            state[str(tran)] = (st.st_size, st.st_mtime)
        except OSError:
            pass
    return state


def _state_changed(s1: dict, s2: dict) -> tuple[bool, list]:
    """두 상태 비교. (변화 있나, 변화 파일 리스트)."""
    changes = []
    keys = set(s1) | set(s2)
    for k in keys:
        if s1.get(k) != s2.get(k):
            changes.append(Path(k).name)
    return (len(changes) > 0, changes)


def wait_for_idle(stability: float = IDLE_STABILITY, verbose: bool = False) -> float:
    """ADE Explorer가 idle될 때까지 대기. stability초 연속 파일 안정.
    Returns: 안정까지 걸린 총 시간(초)."""
    start = time.time()
    last_change = start
    last_state = _capture_state()
    last_print = start

    while True:
        time.sleep(2.0)
        elapsed = time.time() - start
        cur_state = _capture_state()
        changed, what = _state_changed(last_state, cur_state)
        if changed:
            last_change = time.time()
            last_state = cur_state
            if verbose and elapsed - (last_print - start) >= 3:
                w = what[0] if what else "?"
                print(f"  [idle] ... {elapsed:.0f}초  변화: {w} (+{len(what)-1})")
                last_print = time.time()
        else:
            stable_for = time.time() - last_change
            if stable_for >= stability:
                if verbose:
                    print(f"  [idle] ✓ {elapsed:.0f}초 후 안정 ({stability:.0f}초 동안 변화 없음)")
                return elapsed
            if verbose and elapsed - (last_print - start) >= 3:
                print(f"  [idle] ... {elapsed:.0f}초  안정 {stable_for:.1f}/{stability:.0f}초")
                last_print = time.time()


def run_simulation_and_wait(client, timeout: float = 600, verbose: bool = True) -> dict:
    """sevRun + ADE 완전 idle 대기.
    ★ sevRun 전에 먼저 ADE가 idle인지 확인 (이전 시뮬 cleanup 미완 시 모달 방지)."""
    # 0. 시작 전 ADE idle 선확인 — 이전 시뮬 잔여 cleanup 대기
    if verbose:
        print(f"  [run_sim] sevRun 전 ADE idle 확인...")
    pre_idle = wait_for_idle(stability=8.0, verbose=False)
    if verbose:
        print(f"  [run_sim] ADE 준비됨 (선대기 {pre_idle:.0f}초)")

    if verbose:
        print(f"  [run_sim] sevRun 트리거")

    # sevRun (SKILL 한 호출 안에서)
    expr = '''
let((rbResult rbSev)
  rbResult = "no-window"
  foreach(rbW hiGetWindowList()
    let((rbT)
      rbT = hiGetWindowName(rbW)
      when(rbT && index(rbT "ADE Explorer")
        rbSev = car(errset(sevSession(rbW)))
        when(rbSev
          rbResult = car(errset(sevRun(rbSev)))
          when(rbResult == nil rbResult = "sevRun-returned-nil")))))
  rbResult)
'''
    r = client.execute_skill(expr)
    if r.errors:
        return {"status": "error", "msg": f"sevRun 에러: {r.errors}"}
    if verbose:
        print(f"  [run_sim] sevRun 반환: {r.output!r}")
    if "no-window" in r.output or "sevRun-returned-nil" in r.output:
        return {"status": "error", "msg": r.output}

    # ADE idle 대기 (timeout으로 상한)
    start = time.time()
    try:
        last_change = time.time()
        last_state = _capture_state()
        last_print = start
        sim_started = False   # ★ 시뮬이 실제 시작됐다는 증거 (파일 변화 1회 이상)
        MODAL_TIMEOUT = 25.0  # 이 시간 안에 아무 변화 없으면 모달로 안 시작된 것

        while time.time() - start < timeout:
            time.sleep(2.0)
            elapsed = time.time() - start
            cur_state = _capture_state()
            changed, what = _state_changed(last_state, cur_state)
            if changed:
                sim_started = True
                last_change = time.time()
                last_state = cur_state
                if verbose and elapsed - (last_print - start) >= 3:
                    w = what[0] if what else "?"
                    print(f"  [run_sim] ... {elapsed:.0f}초  변화: {w}{' +'+str(len(what)-1) if len(what)>1 else ''}")
                    last_print = time.time()
            else:
                # ★ 시뮬 시작 증거 없이 MODAL_TIMEOUT 경과 → 모달로 안 시작됨
                if not sim_started and elapsed >= MODAL_TIMEOUT:
                    if verbose:
                        print(f"  [run_sim] ⚠ {elapsed:.0f}초간 변화 없음 — 시뮬 미시작(모달 의심)")
                    return {"status": "not_started", "elapsed": elapsed,
                            "msg": "시뮬 시작 증거 없음 (모달 또는 sevRun 무시)"}
                # 시작은 했고, 이제 안정되면 완료
                if sim_started:
                    stable_for = time.time() - last_change
                    if stable_for >= IDLE_STABILITY:
                        if verbose:
                            print(f"  [run_sim] ✓ {elapsed:.0f}초  ADE idle 확정")
                        psf = None
                        psf_size = 0
                        for tran in SIM_BASE.rglob("tran.tran.tran"):
                            if "_deleted" in str(tran):
                                continue
                            try:
                                mt = tran.stat().st_mtime
                                if mt >= start - 5:
                                    if not psf or mt > psf.stat().st_mtime:
                                        psf = tran
                                        psf_size = tran.stat().st_size
                            except OSError:
                                pass
                        history = psf.parents[2] if psf else None
                        return {
                            "status": "ok", "elapsed": elapsed,
                            "history_dir": str(history) if history else None,
                            "psf_size": psf_size,
                        }
                    if verbose and elapsed - (last_print - start) >= 3:
                        print(f"  [run_sim] ... {elapsed:.0f}초  안정 {stable_for:.1f}/{IDLE_STABILITY:.0f}초")
                        last_print = time.time()

        return {"status": "timeout", "elapsed": timeout}
    except Exception as e:
        return {"status": "error", "msg": str(e)}


if __name__ == "__main__":
    from vb_connect import get_client
    c = get_client()
    print("=== run_sim.py 자기검증 (적응형 idle 감지) ===")
    result = run_simulation_and_wait(c, timeout=120)
    print(f"\n결과: {result}")
    if result.get("status") == "ok":
        from measure import measure_latest
        m = measure_latest()
        print(f"\n측정:")
        print(f"  freq  = {m['freq']/1e9:.4f} GHz")
        print(f"  I_avg = {m['i_avg']*1e6:.4f} uA")
        print(f"  FoM   = {m['fom']:.4e}")
