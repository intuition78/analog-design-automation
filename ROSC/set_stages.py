"""set_stages.py — SIM_ROSC의 ROSC 인스턴스 단 수 N 설정 (schCheck 포함).

  set_n_stages(client, n)
    → I0<N:1> 인스턴스 + 4개 라벨 갱신 + schCheck + 저장.

★ 교훈: schCheck 안 부르면 Maestro가 'modified since extraction'으로 시뮬 거부.
"""
LIB, CELL = "test_jhyang2", "SIM_ROSC"


def _labels_for(n: int) -> list[str]:
    mid = n - 1
    return [
        f"CLK,A<{mid}:1>",
        f"A<{mid}:1>,CLK",
        f"<*{n}>net2",
        f"<*{n}>VSS",
    ]


def get_current_n(client) -> int:
    r = client.execute_skill(
        f'car(setof(rbX dbOpenCellViewByType("{LIB}" "{CELL}" "schematic")~>instances '
        f'rbX~>baseName=="I0"))~>numInst'
    )
    return int(r.output)


def set_n_stages(client, n: int) -> dict:
    old_n = get_current_n(client)
    if old_n == n:
        # 변경 없어도 schCheck는 한 번 돌려놓음 (이전 변경이 안 처리됐을 수 있음)
        client.execute_skill(
            f'let((cv) cv=dbOpenCellViewByType("{LIB}" "{CELL}" "schematic" "" "a") '
            f'schCheck(cv) dbSave(cv))'
        )
        return {"before": old_n, "after": n, "status": "no-change"}

    old_lbl = _labels_for(old_n)
    new_lbl = _labels_for(n)

    label_changes = "".join(
        f'foreach(rbS cv~>shapes '
        f'  when(rbS~>objType=="label" && rbS~>theLabel=="{o}" '
        f'    rbS~>theLabel="{nw}")) '
        for o, nw in zip(old_lbl, new_lbl)
    )

    expr = (
        f'let((cv ig) '
        f'cv=dbOpenCellViewByType("{LIB}" "{CELL}" "schematic" "" "a") '
        f'ig=car(setof(rbX cv~>instances rbX~>baseName=="I0")) '
        f'ig~>name="I0<{n}:1>" '
        f'{label_changes}'
        f'schCheck(cv) '       # ← Maestro가 시뮬 거부하지 않도록 필수
        f'dbSave(cv) "ok")'
    )
    r = client.execute_skill(expr)
    if r.errors or (r.output and "ok" not in r.output):
        return {"before": old_n, "after": old_n, "status": f"FAIL: {r.errors or r.output}"}

    final = get_current_n(client)
    return {"before": old_n, "after": final,
            "status": "ok" if final == n else f"mismatch: requested {n}, got {final}"}


if __name__ == "__main__":
    from vb_connect import get_client
    c = get_client()
    print("현재 단 수:", get_current_n(c))
    print("\n[테스트] 51 -> 23 -> 51 왕복")
    print("   set 23:", set_n_stages(c, 23))
    print("   set 51:", set_n_stages(c, 51))
