# analog-design-automation
analog design automation
PROJECT_LOG.md — 아날로그 회로 설계 자동화 프로젝트

목적: 새 세션의 Claude가 이 파일 하나로 전체 맥락·노하우·함정을 복원해
직전 세션과 동일한 퍼포먼스를 내는 것. AI는 세션이 바뀌면 기억을 잃으므로
이 파일이 유일한 진실의 원천이다.
새 세션 시작 시: "Bridge 폴더의 PROJECT_LOG.md 읽고 시작해줘" + 이 내용 전체 붙여넣기.
(Claude는 사용자의 Linux 박스 파일을 직접 못 읽음 → 사용자가 붙여넣어야 함)

최종 업데이트: 2026-06-02 (ROSC 자율 최적화 완성 N=31, OTA 자동설계 단계 진입)
═══════════════════════════════════════════════════════════════════════════
0. 프로젝트 목표 (장기, 수개월)
═══════════════════════════════════════════════════════════════════════════
아날로그 회로 설계 자동화:

회로 스키매틱 자동 생성 + 배선 + 심볼 (예: folded cascode OTA)
테스트벤치 + 시뮬레이션 자동화 (Spectre/Maestro/ADE Explorer)
파라미터 최적화 루프 — 수시간 이터레이션, 결정론적 .py
레이아웃 생성

완료된 서브목표: 링오실레이터(ROSC) 단 수 N 최적화로 FoM=freq/(I_avg×VDD) 극대화.
→ N=31이 최적 (FoM 8.88e+13). 자율 sweep 24.6분 24평가로 발견 + 자동 적용 완료.
현재 단계: folded cascode OTA 자동 스키매틱 생성 (Phase 1 막힘 — §8 참조).
도구: virtuoso-bridge-lite v0.6.0 (github.com/Arcadia-1/virtuoso-bridge-lite)
═══════════════════════════════════════════════════════════════════════════
1. 작업 환경 (★ 함정이 핵심 ★)
═══════════════════════════════════════════════════════════════════════════

접속: Windows → Exceed TurboX(ETX) → Linux
Virtuoso: IC23.1 (ISR17), RHEL8
시뮬: ADE Explorer 경유 Spectre (/appl/LINUX/opus514/tools/bin/spectre)
PDK: Samsung SF2 (sf2pp), 트랜지스터 = PCDF 디바이스 sf_ac_mos
계정: j27.yang
Python: /appl/CAEutil/LINUX8/local/Python/Python-3.13.12/bin/python3.13
(★ python 없음! 반드시 python3.13 전체 경로)
virtuoso-bridge: v0.6.0
프로젝트 폴더: /user/adtco/USER/j27.yang/Bridge/
시뮬 결과 base: /user/adtco/USER/j27.yang/j27.yang+ss_isen1_sf2pp_5108202+MPW11+3/simulation/test_jhyang2/
라이브러리: test_jhyang2
쉘: csh/tcsh (★ bash 문법 자주 안 먹음)

★ 이 환경의 결정적 특성 ★

터미널(vwpl330ev05 고정)과 Virtuoso(노드 매번 바뀜)가 다른 머신.

노드 간 SSH 차단(Connection refused). 임의 TCP 포트는 통함.
파일시스템 공유(/user/...) → 노드명/결과/마커 파일 공유에 활용.


표준 virtuoso-bridge start(SSH터널) 못 씀. TCP 직접 접속으로 우회.
v0.6.0 run_and_wait 못 씀 (SSH 폴링 필요).
포트 48000 사용 중 (빈 포트 직접 검증함).
psf 변환 유틸이 32비트 옛 바이너리 → 라이브러리 심링크 필요 (§5-E).

═══════════════════════════════════════════════════════════════════════════
2. 연결 방법 (작동 검증됨)
═══════════════════════════════════════════════════════════════════════════
CIW에서 vb_setup.il 로드 → 데몬 기동(48000) + 노드명을 bridge_endpoint.txt에 기록
→ 터미널 vb_connect.py가 읽어 자동 연결.
매 세션 재시작 (README.md 참조)

CIW: load("/user/adtco/USER/j27.yang/Bridge/vb_setup.il")
Python 스크립트 안: from vb_connect import get_client; c = get_client()
검증: python3.13 vb_connect.py → "연결 성공" + 노드:포트 출력

═══════════════════════════════════════════════════════════════════════════
3. 파일 목록 (/user/adtco/USER/j27.yang/Bridge/)
═══════════════════════════════════════════════════════════════════════════
인프라
파일역할README.md재시작 3단계PROJECT_LOG.md이 문서vb_setup.il(CIW용) 데몬 기동 + endpoint 기록vb_connect.py자동 연결 get_client()bridge_endpoint.txt노드:포트 자동 갱신_libs/32비트 라이브러리 심링크 (libnsl.so.1, libstdc++.so.5)_archive/84개 진단/단계 스크립트 보관 (필요시 grep)
ROSC 자동화 자산 (모두 검증 완료 ✅)
파일역할make_inv_chain.pyN단 인버터 체인 별도 셀 생성. 새 셀 생성 패턴의 원본set_stages.pySIM_ROSC 단 수 변경 + schCheck + dbSaverun_sim.pysevRun + ADE idle 적응 감지 + 모달 조기감지measure.pyPSF 파싱 + freq/jitter/duty/i_avg/FoMadaptive_evaluator.py적응형 tran + 5분류(degenerate 포함) + 재시도auto_optimizer.pyBinary(경계) + Ternary(피크) + 무한루프방지 + best_n 적용
OTA 자동화 자산 (작성 중)
파일역할상태fca_spec.pyfolded cascode 회로 명세 (15 TR, 넷, 변수)✅ 검증fca_build.py스키매틱 자동생성 Phase1(배치)/2(핀)/3(와이어)⚠ 셀생성 막힘(§8)
═══════════════════════════════════════════════════════════════════════════

4. ★★★ 반드시 지킬 교훈 (SKILL/csh/PCDF) ★★★
═══════════════════════════════════════════════════════════════════════════
A. SKILL 작성

예약어 변수명 금지: t(=true), nil, car, list. → 접두사 rbX 사용 (rbInst, rbCv 등).
복잡한 다중표현식 SKILL 피함. 브릿지가 /tmp/*.il로 만들어 load → 깨지기 쉬움.
계산·로직은 Python, SKILL엔 단순 명령만.
함수 시그니처 추측 금지. arglist('함수명) 확인.
DB 객체 구조 모르면 obj~>? 로 속성 목록.
execute_skill은 Python 반환만, CIW엔 안 찍힘.
csh: 2>&1/sed -i/heredoc(<<)/2>/dev/null/xargs -I{} 안 먹는 경우 많음.
막히면 bash 들어가서 실행.
^M 문제: Windows→Linux 붙여넣기 시 CR 남음. vi :set ff=unix 후 저장,
또는 tr -d '\r'. 붙여넣기 전 vi :set paste 필수 (자동 들여쓰기 방지).
긴 코드 붙여넣기: vi :1,$d로 비우고 → :set paste → i → 붙여넣기 →
Esc → :set ff=unix → :wq. 붙여넣기 후 끝까지 스크롤해 잘림 확인.

B. PCDF 디바이스 (sf_ac_mos)

PMOS = model slvtpfet, NMOS = model slvtnfet.
트랜지스터 사이즈는 stack(=length)과 fingers(=width)로 조절 (continuous 아닌 discrete 정수).
schCreateInst로 master(sf2pp/sf_ac_mos/symbol) 재사용 시 model이 nfet 기본값으로 떨어짐
→ 교정 필수: rbInst~>model = "slvtpfet" + errset(CCSinvokeCdfCallbacks(rbInst)).
터미널은 g/d/s/b 이름으로 식별 (좌표 X — 복제 시 d/s 위치 반전됨).

C. 셀 복사 후 클린업

shape 삭제: objType ∈ {line, ellipse, label, textDisplay}
핀 인스턴스 삭제: cellName ∈ {iopin, ipin, opin}

★ 검증된 SKILL 패턴 (재사용) ★
skill; 새 셀 생성/열기 — ★ mode "a"가 정답 ("w"는 nil 반환!) — 단 §8 함정 주의
dbOpenCellViewByType("test_jhyang2" "CELL" "schematic" "" "a")
; 인스턴스 (master 재사용 → PCDF 보존)
schCreateInst(cv master "이름" list(x:y) "R0")
; 와이어
schCreateWire(cv "route" "full" list(p1 p2) 0 0 0 nil nil)
; 와이어 라벨 (net 이름)
schCreateWireLabel(cv nil 점 "넷이름" "centerCenter" "R0" "stick" 0.05 nil)
; 핀 (ipin/opin/iopin)
schCreatePin(cv dbOpenCellViewByType("basic" "ipin" "symbol") "이름" "input" nil x:y "R0")
; 심볼 자동생성
schPinListToSymbol(lib cell "symbol" schSchemToPinList(lib cell "schematic"))
; PCDF model 교정
errset(CCSinvokeCdfCallbacks(rbInst))
; ★ sevRun은 SKILL 한 호출 안에서:
let((rbS) rbS = sevSession(rbW) sevRun(rbS))
; tran 변경
maeSetAnalysis("test_jhyang2_SIM_ROSC_1" "tran" ?options `(("stop" "30n")) ?session "fnxSession1")
═══════════════════════════════════════════════════════════════════════════
5. ★★★ ADE Explorer 시뮬 자동화 — 핵심 노하우 ★★★
═══════════════════════════════════════════════════════════════════════════
A. 시뮬 실행 — sevRun 필수

★ 창 제목이 "ADE Explorer"면 maeRunSimulation이 가짜 모드(.RO)로만 돎.
→ 반드시 sevRun(sevSession(window)) 사용.
sev 객체를 Python으로 빼내면 "unbound variable" 에러 → SKILL 한 호출 안에서 처리:
let((rbS) rbS = sevSession(rbW) sevRun(rbS))
세션 식별자(fnxSessionN)는 매번 바뀜 → 하드코딩 금지, 창 제목 "ADE Explorer" 매칭으로 동적 탐색.
sevRun 반환값은 history 번호 같은 숫자 (예 '85'). 의미 없음 — 신호는 결과 파일로 확인.

B. ★★ schCheck 누락 함정 (큰 시간 낭비 주의)

SKILL로 schematic 수정 후 schCheck(cv) + dbSave(cv) 안 부르면
Maestro가 'modified since extraction' 에러로 시뮬 거부.
set_stages.py에 자동 포함됨.

C. ★★★ ADE idle 적응 감지 (모달 함정의 근본 해결)

★ .simDone/logStatus는 Spectre 자체의 종료 신호 — ADE Explorer는 그 후
~15초 더 결과 DB cleanup. Spectre 끝 ≠ ADE idle.
★ 진짜 ADE idle = 모든 결과 파일이 N초 연속 mtime/size 변화 없음 (시간 하드코딩 X):

관찰: ExplorerRORun.0.RO.log(84B→330B 점프 시 완료인식), .rdb, .msg.db,
.rdb-journal, tran.tran.tran
IDLE_STABILITY=10초 연속 무변화 → idle 확정. 시뮬 길이/회로 종류 무관.


run_sim.py에 구현. 이게 모달 함정의 핵심 해결책.

D. ★★ 모달 다이얼로그 (예방이 유일 해결)

"modified since last extraction" / "Cannot run new simulation" 모달 뜨면
모든 SKILL 응답 불가.
dismiss 자동 처리 불가 (CLI는 DISPLAY 없음, SKILL hi*Dismiss 0개).
★ 예방책 (run_sim.py 구현됨):

sevRun 전 ADE idle 선확인 (이전 시뮬 cleanup 대기) — wait_for_idle(8)
모달 조기 감지: sevRun 후 25초간 파일 변화 0 → "not_started"로 빠르게 실패
(229초 매달림 방지). 시작 증거(파일 변화 1회) 없이는 idle 판정 안 함.


이 두 보강으로 24회 연속 sweep이 모달 없이 완주함.

E. ★ PSF 결과 파싱

결과 위치 (덮어쓰기):
<base>/SIM_ROSC/maestro/results/maestro/ExplorerRORun.0.RO/1/test_jhyang2_SIM_ROSC_1/psf/tran.tran.tran

GUI run + sevRun 둘 다 ExplorerRORun.0.RO로 덮어씀. 옛것은 _deleted_XXXXX (무시).


psf 변환 유틸 (32비트 옛 바이너리): /appl/LINUX/opus514/tools/dfII/bin/psf

libnsl.so.1 → /usr/lib/libnsl.so.2.0.0, libstdc++.so.5 →
/appl/LINUX/opus514/tools.lnx86/lib/libstdc++.so.5.0.3
둘 다 Bridge/_libs/에 심링크 + LD_LIBRARY_PATH 지정. measure.py의 psf_bin_to_ascii.


v0.6.0 parse_spectre_psf_ascii가 group 형식 불완전 (첫 컬럼만 읽음).
→ 우회: TRACE에서 신호 순서 추출 + VALUE 전체 숫자 정규식 → (N_time, 1+N_sig) reshape.
measure.py의 parse_psf_value.

═══════════════════════════════════════════════════════════════════════════

6. ★★★ 자율 측정 분류 + 적응형 tran (완성, 검증) ★★★
═══════════════════════════════════════════════════════════════════════════
measure.py 측정 지표

freq: VDD/2 상향교차 평균 주기의 역수 (startup_frac=0.3, 앞 30% 제외)
n_periods: 측정 구간의 주기 수
jitter: 주기 변동계수(std/mean). 단일모드 ~0%, 다중모드 큼
duty: high시간/주기 (정상 ROSC ~50%)
duty_std: 듀티 표준편차. 다중모드면 큼
clk_swing, i_avg(=V0:p 평균)

★★ 5분류 (adaptive_evaluator.classify)

no_osc: 교차 ≤1 AND swing < 0.21V (VDD×0.3) → 발진 X
degenerate: n_periods≥10 AND (jitter≥15% OR duty<30% OR duty>70% OR duty_std≥15%)
→ 다중모드/깨진 발진. 클럭 부적합. FoM=0 처리. 재시도 안 함.
good: n_periods≥30 AND jitter<15% → 채택
marginal: 발진 정상이나 주기 부족(3~29) → tran 재계산 재시도
insufficient: 교차 매우 적음 → 재시도

★★★ 다중모드(고차모드) 발진 — 중요 물리현상

큰 N에서 ROSC가 단일 360° 모드가 아니라 3차/5차 고조파 모드로 발진.
파형: 기본 주기 안에 high→low→high 추가천이 → 교차수 3배 → freq 측정이 3배로 잡힘.
N=255 실측: 육안 680MHz인데 measure 2.06GHz(3배), jitter 27%, duty 51%±28% → degenerate.
→ 옵티마이저가 자동 회피 (FoM=0). 측정 신뢰성 문제 해결.

★★ 적응형 tran (사용자 설계 — 비례 재계산)

첫 시도: 이전 good 없으면 TRAN_INIT=10ns(짧게 시작).
있으면 가장 가까운 good N의 실측으로 외삽 (freq∝1/N → 100단→50단이면 tran 절반).
재계산 (주기 부족 시): "방금 N주기 봤고 목표 30주기면 → ×(30/N) + 마진 20%".
예: 3주기→×12배, 21주기→×1.7배. 한 번에 정확히 점프.
TRAN_MARGIN=1.2 (아슬아슬 29주기 방지). TRAN_STARTUP_FRAC=0.4. MAX_ATTEMPTS=4. TRAN_MAX=3000ns.
검증: N=51 첫 10ns→21주기(marginal)→×1.7→17ns→38주기(good). freq 일관 3.4GHz.

═══════════════════════════════════════════════════════════════════════════
7. SIM_ROSC 테스트벤치 + auto_optimizer + 결과
═══════════════════════════════════════════════════════════════════════════
SIM_ROSC 구조

I0<51:1>: ROSC 인스턴스 직렬 (baseName=I0, numInst=51)
V0=vpwl (VDD 0→0.7V ramp), V1=vdc, IPRB0=iprobe
핀: CLK, VDD, VSS, IBIAS, A<1>~A<N-1>
라벨 N-의존: IN="CLK,AN-1:1", OUT="AN-1:1,CLK", VDD="<*N>net2", VSS="<*N>VSS"
★ N=1 함정: A<0:1> 빈 버스 → netlist 깨짐. 시작 N≥3.
단 수 변경(set_stages.py): inst~>numInst 직접대입 안 먹음 →
inst~>name="I0<N:1>" 변경하면 numInst+instTerms 자동 따라감 + 4개 라벨 갱신 + schCheck + dbSave.

auto_optimizer.py 알고리즘

Phase 1: Binary search로 발진 가능 최소 N(경계) 발견
Phase 2: Ternary search로 FoM 피크 발견
★ 무한루프 방지: prev_m1/m2 기억해 진전 없으면 종료 + max_iters=20 안전망 + 캐시
끝나면 best_n으로 schematic 자동 적용

★ ROSC 최종 결과 (자율 sweep 24.6분, 24평가) ★
N=31:  freq=5.6036 GHz  I=90.12µA  Power=63.08µW  FoM=8.883e+13 ★ 최적(발진경계)
N=33:  5.26GHz  FoM=8.34e+13
N=51:  3.40GHz  FoM=5.33e+13 (baseline)
N=101: 1.72GHz  FoM=2.62e+13
N=131: 1.33GHz  FoM=1.99e+13
N=181, 255: degenerate (다중모드) → FoM=0 자동 거름
N≤29: no_osc (게인 부족)
★ 물리 인사이트 (사용자에게 설명 검증됨)

I_avg ≈ C·VDD/(2τ), N에 무관 (충전 전하 N배 × 빈도 1/N배 상쇄). 실측 90~95µA 일정.
freq ∝ 1/N (링 한 바퀴 = 2Nτ).
FoM = freq/(I·VDD) = 1/(N·C·VDD²) ∝ 1/N → N 작을수록 좋음.
→ 발진 가능 최소 N = 최적 (=N=31). 더 줄이면 이득 부족으로 발진 정지.
FoM은 사실상 "한 사이클당 에너지의 역수" = 에너지 효율.
(실무: 발진경계는 PVT에 취약해 보통 마진 둠. robustness 항 추가하면 자동 처리 가능)

═══════════════════════════════════════════════════════════════════════════

8. ★ 현재 단계: Folded Cascode OTA 자동 설계 (진행 중) ★
═══════════════════════════════════════════════════════════════════════════
설계 결정 (사용자와 확정)

토폴로지: 기본 single-ended 출력 folded cascode, PMOS input pair, NMOS folding.
Bias: ideal 전압원 금지. analogLib idc 1개(IBIAS, 1µA)만 사용.
IBIAS가 4-TR diode 스택(MB1~MB4)을 통해 흘러 모든 bias 전압 생성.
전류 흐름: VDD→MB1→MB2→MB3→MB4→IBIAS(외부 idc로)→VSS.
★ 단일출력이라 P_load 한쪽(M9)이 diode-connected → bias 자동 생성. 외부 bias 3종.
셀 이름: 메인 FCA_main, 테스트벤치 FCA_TB (라이브러리 test_jhyang2).
매칭: 왼쪽=오른쪽 페어만 (M1=M2, M9=M10, M7=M8, M5=M6, M3=M4).
추가 제약: cascode TR(M5/M6/M7/M8)의 stack(length)=1 고정.
cascode width = load width 강제 (P: M7/M8 fingers = M9/M10 fingers,
N: M5/M6 fingers = M3/M4 fingers).
Current mirror 비율: 변수(fingers)의 비율로 자동 결정. BO가 전체 전류 알아서 정함.
Branch 전류 균형: BO에 맡김 (명시 제약 X, saturation check로 페널티).
배치: 좌측 column / 중앙 bias 스택 / 우측 column (좌우 대칭).
배선: 사람처럼 net label 명시 (각 터미널 stub + 라벨, 같은 라벨끼리 자동 연결).

트랜지스터 15개 (fca_spec.py에 명세 — 검증됨)
메인 11: M1/M2(input pair, g=INP/INN d=DRN_L/OUT s=TAIL b=VDD),
MTAIL(g=VBP_TAIL d=TAIL s=VDD), M9(P load diode, g=d=NCASC_L s=VDD),
M10(P load mirror, g=NCASC_L d=NCASC_R s=VDD), M7/M8(P cascode, g=VBP_CASC
d=DRN_L/OUT s=NCASC_L/NCASC_R), M5/M6(N cascode, g=VBN_CASC d=DRN_L/OUT
s=M3_DRN/M4_DRN), M3/M4(N load, g=VBN_LOAD d=M3_DRN/M4_DRN s=VSS).
Bias 4: MB1(P, g=d=VBP_TAIL s=VDD), MB2(P, g=d=VBP_CASC s=VBP_TAIL),
MB3(N, g=d=VBN_CASC s=VBN_LOAD), MB4(N, g=d=VBN_LOAD s=IBIAS).
★ 단일출력: M2 drain = OUT (별도 DRN_R 노드 없음).
외부 핀 6개
INP(input), INN(input), OUT(output), VDD(inputOutput), VSS(inputOutput), IBIAS(inputOutput)
최적화 변수 10개 (모두 정수)
v_in_stack(1-4), v_in_fingers(1-32), v_tail_stack(1-4), v_tail_fingers(1-32),
v_pload_stack(1-4), v_p_fingers(1-32, P cascode+load 공통),
v_nload_stack(1-4), v_n_fingers(1-32, N cascode+load 공통),
v_bias_out_stack(1-4), v_bias_fingers(1-32, bias 4개 공통).
★ 현재 막힌 지점 (다음 세션 즉시 할 일) ★

fca_build.py Phase 1에서 dbOpenCellViewByType("test_jhyang2" "FCA_main" "schematic" "" "a")가 nil 반환.
원인: FCA_main 셀이 아직 없어서 mode "a"가 자동 생성 안 함.
(mode "w"도 nil, dbCreateCellView는 IC23.1에 undefined 함수)
★ 해결책: 사용자가 Virtuoso GUI Library Manager에서 빈 FCA_main schematic을
수동 생성 (File→New→Cell View, Cell=FCA_main, View=schematic, Type=schematic) →
저장·닫기 → 그 후 fca_build.py 재실행하면 mode "a"가 기존 빈 셀을 채움.
또는 schHiCreateCellView("test_jhyang2" "FCA_main" "schematic" "schematic" t) SKILL 시도 (미검증).

OTA 시뮬 계획 (PENDING)

DC sim: 모든 TR saturation 체크 (region==2 또는 vds>vgs-vth AND vgs>vth).
OUT은 DC에서 floating → testbench에서 OUT을 적절한 DC bias로 설정 필요.
AC sim: DC gain(저주파 magnitude), BW(-3dB).
온도 상온, tt 코너 (기존 SIM_ROSC 환경 재사용).
FoM = (DC_gain_linear × BW) / Power.
★ 하드리밋: dc_gain_dB ≥ 30 AND BW ≥ 1MHz (반드시 만족, 위반시 큰 페널티).
최적화: BO (scikit-optimize gp_minimize 또는 TuRBO) — 10변수 이산, 평가 비쌈(~30초).
약 100~150회 시뮬 ≈ 75분/run 예상.
testbench: ideal voltage source 1V, idc 1µA, ground, iprobe(전류측정).
최종: 최적 파라미터를 FCA_main(테스트벤치 아닌 앰프)에 적용.

═══════════════════════════════════════════════════════════════════════════
9. LLM의 역할 (사용자와 합의한 구도)
═══════════════════════════════════════════════════════════════════════════

결정론적 .py 우세: 수치 최적화(ternary/TuRBO), 측정/파싱, 수렴 판정. (ROSC가 이 영역)
LLM 진짜 가치: ①측정 이상 진단(증상→원인, 예: 다중모드 발견) ②회로 위상 선택(이산 설계결정)
③자연어 명세→구조화 스펙 ④실패 복구 휴리스틱 ⑤결과 물리 해석.
구도: LLM "오케스트레이터/판단노드" + .py "근육/실행엔진".
LLM은 검증된 빌딩블록 조합·선택, .py가 정밀 실행. 폐쇄망 LLM 약하면 자유도 줄이고 선택지 제공.

═══════════════════════════════════════════════════════════════════════════
10. 사용자 작업 패턴/원칙
═══════════════════════════════════════════════════════════════════════════

붙여넣기 텍스트 길이 제한(보안) — 여러 조각 분할 가능.
한 번에 한 단계씩 검증 선호.
★ 강한 원칙: 하드코딩/하드리밋 금지, 적응형으로 (시간 하드코딩 대신 신호 기반).
★ 반복 개입 최소화 (토큰 절약 — 문제는 모아서 한 번에 보고, 코드는 한 번에 완성).
회로지식 풍부 — degenerate(다중모드) 발견, bias 노드 정확히 짚음, 적응형 tran 설계.
검증은 GUI 육안 + 측정값 양쪽으로.

═══════════════════════════════════════════════════════════════════════════

11. 새 세션 재개 매뉴얼
═══════════════════════════════════════════════════════════════════════════

README.md 절차로 브릿지 연결 (vb_setup.il load → vb_connect.py 검증).
이 PROJECT_LOG.md 통째로 Claude에게 붙여넣기.
진행 지점 지정. 현재: "ROSC 완성(N=31). OTA fca_build.py Phase1 막힘 —
FCA_main 빈 셀 수동 생성 후 재시도부터" (§8 참조).
Claude가 컨텍스트 복원 + 다음 코드 작성.

즉시 다음 액션 (§8)

사용자가 GUI Library Manager에서 빈 FCA_main schematic 수동 생성 (1분).
python3.13 fca_build.py 실행 (Phase 1~3 한 번에: 트랜지스터15 + 핀6 + 와이어/라벨).
GUI에서 시각 확인 (배치/대칭/PMOS·NMOS종류/핀/net label/회로 연결).
문제점 한 번에 모아 보고 → 일괄 수정.
통과 후: 심볼 생성 → FCA_TB testbench → DC sim(saturation) → AC sim(gain/BW) → BO 옵티마이저.
