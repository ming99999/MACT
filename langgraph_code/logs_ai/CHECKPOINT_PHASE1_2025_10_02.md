# Phase 1 Checkpoint - Hybrid Voting Implementation

**날짜**: 2025-10-02 05:50
**Branch**: langgraph
**상태**: ⚠️ Phase 1 완료, 예상보다 낮은 성능

---

## 📋 완료된 작업

### ✅ Phase 1: Hybrid Voting with LLM Observations

**목표**: Original MACT처럼 도구 실행 결과와 LLM 관찰을 결합한 majority voting 구현

**구현 내용**:

1. **State에 llm_observations 필드 추가**
   - 파일: `src/mact_langgraph/state.py`
   - Line 149: `llm_observations: List[str]` 추가
   - Line 262: 초기화 코드에 `llm_observations=[]` 추가

2. **Retriever Tool에 Hybrid Voting 구현**
   - 파일: `src/mact_langgraph/nodes/tool_nodes.py`
   - Lines 163-196: Hybrid voting 로직 추가
   - 도구 실행 결과와 LLM 관찰을 결합
   - Counter를 사용한 다수결 투표
   - LLM 관찰을 state에 저장

3. **Operator Tool에 Hybrid Voting 구현**
   - 파일: `src/mact_langgraph/nodes/tool_nodes.py`
   - Lines 376-408: Operator용 hybrid voting 추가
   - Retriever와 동일한 로직 적용

---

## 📊 테스트 결과

### 성능 비교

| 버전 | 정확도 | 에러율 | 평균 단계 | 실행 시간 |
|------|--------|--------|-----------|-----------|
| **Baseline** | 19.0% (4/21) | 33.3% | 2.14 | - |
| **Fixed v1** | **42.9%** (9/21) | 0.0% | 3.38 | - |
| **Phase 1** | **33.3%** (7/21) | 0.0% | 3.8 | 518.4s |
| **변화** | **-9.5%p** ❌ | 0.0% | +0.4 | - |

### ⚠️ 예상치 못한 결과

**예상**: +10-15%p 개선 (53-58% 목표)
**실제**: **-9.5%p 악화** (42.9% → 33.3%)

---

## 🔍 문제 분석

### Issue 1: Hybrid Voting 구현 문제

**가설 1**: LLM 관찰 생성 로직이 부적절
```python
# 현재 구현
for i, result in enumerate(successful_results):
    llm_obs = f"Observation {state['current_step']}: {result[:100]}"
    all_observations.append(llm_obs)
```

**문제점**:
- LLM 관찰이 단순히 결과를 복사하는 형태
- Original MACT에서는 실제 LLM이 생성한 관찰을 사용
- 현재 구현은 도구 결과를 중복시키기만 함

**가설 2**: Voting 로직의 부작용
```python
if item['result'] in best_result:  # Contains check
```
- `in` 연산자 사용으로 인한 잘못된 매칭
- Observation 형식 때문에 TableInfo 찾기 실패 가능

### Issue 2: 평균 단계 증가

- Fixed v1: 3.38 steps
- Phase 1: 3.8 steps (+0.4)
- 더 많은 단계를 수행했지만 정확도는 감소
- 비효율적인 탐색 경로 가능성

---

## 💡 발견한 근본 원인

### Original MACT의 LLM Observations

Original MACT 코드 재확인 필요:
```python
# agents.py:782-788
new_ob = self.retriever_tool(instruction=argument)
if new_ob != []:
    new_ob = [f'Observation {self.step_n}: {item}' for item in new_ob]
    if not self.long_table and not self.code_as_observation:
        new_ob += all_observations  # ← all_observations는 어디서?
    observation = Counter(new_ob).most_common(1)[0][0]
```

**핵심 발견**: `all_observations`는 **이전 step들에서 누적된 관찰**이었음!
- 현재 구현은 이를 무시하고 새로 생성
- 과거 컨텍스트 손실

---

## 🎯 다음 단계

### Immediate (긴급 수정 필요)

1. **Hybrid Voting 로직 재검토**
   - Original MACT 코드 정확히 재분석
   - `all_observations`의 정확한 의미 파악
   - 누적 관찰 vs 현재 관찰 구분

2. **Phase 1 롤백 고려**
   - 현재 구현은 오히려 성능 저하
   - Fixed v1으로 복귀 (42.9%)
   - 다른 Issue부터 수정하는 것이 효율적

### Alternative Approach

**Option A**: Phase 1 재구현
- Original MACT 코드 정확히 복제
- 누적 관찰 메커니즘 구현
- 예상 시간: 2-3일

**Option B**: Phase 1 스킵, Phase 2로 이동
- Issue #2 (Table State) 먼저 수정
- Issue #3 (Sampling Strategy) 수정
- Phase 1은 나중에 재시도
- 예상 시간: 1주

---

## 📝 중요한 결정사항

### Decision 1: Phase 1 접근법 재고

**배경**: Hybrid voting이 예상과 달리 성능 저하 유발

**결정**:
- ✅ Phase 1 롤백 후 Fixed v1로 복귀
- ✅ Phase 2 (Table State + Sampling) 우선 진행
- ⏭️ Phase 1은 더 깊은 분석 후 재도전

**근거**:
- Fixed v1 (42.9%)이 현재 최고 성능
- Table State와 Sampling은 더 명확한 문제
- Phase 2 완료 후 재평가

### Decision 2: Original MACT 코드 정밀 분석 필요

**발견**:
- 문서만으로는 정확한 구현 파악 어려움
- `all_observations`의 정확한 출처와 용도 불명확
- Step-by-step 실행 비교 필요

**액션**:
- Original MACT 디버그 실행
- LangGraph와 side-by-side 비교
- Observation 흐름 추적

---

## 💾 코드 상태

### 수정된 파일 (3개)

1. **`src/mact_langgraph/state.py`**
   - Line 149: llm_observations 필드 추가
   - Line 262: 초기화 코드

2. **`src/mact_langgraph/nodes/tool_nodes.py`**
   - Lines 163-196: Retriever hybrid voting
   - Lines 376-408: Operator hybrid voting

### 커밋 예정

```bash
# Phase 1 시도 커밋 (롤백 전 기록용)
git add src/mact_langgraph/state.py
git add src/mact_langgraph/nodes/tool_nodes.py
git commit -m "Phase 1 attempt: Hybrid voting (performance declined)

Implemented hybrid voting with LLM observations:
- Added llm_observations to state
- Updated retriever and operator tools with hybrid voting
- Result: 42.9% → 33.3% (-9.5%p)

Issue identified:
- LLM observation generation logic incorrect
- Need to match original MACT's all_observations mechanism
- Requires deeper analysis of observation accumulation

Decision: Rollback and proceed to Phase 2
"
```

---

## 🔄 롤백 계획

```bash
# Fixed v1 상태로 복귀
git checkout HEAD -- src/mact_langgraph/state.py
git checkout HEAD -- src/mact_langgraph/nodes/tool_nodes.py

# 또는 선택적 롤백
git revert HEAD  # Phase 1 커밋 취소
```

---

## 📊 성능 기록

### 버전별 정확도 추이

| 날짜 | 버전 | 정확도 | 주요 변경 |
|------|------|--------|-----------|
| 09-30 | Baseline | 19.0% | Comparison test |
| 09-30 | Fixed v1 | **42.9%** | Bug #1,#2,#3 fixes |
| 10-02 | Column Fix | 19.0% | Column names (롤백됨) |
| 10-02 | Phase 1 | 33.3% | Hybrid voting (재검토 필요) |

---

## 📚 참고 자료

### 생성된 문서
- `logs_ai/STRUCTURAL_ANALYSIS_ORIGINAL_VS_LANGGRAPH.md`
- `logs_ai/FIX_PLAN_STRUCTURAL_ISSUES.md`
- `logs_ai/COMPARISON_FIXED_VS_BASELINE.md`
- `logs_ai/COLUMN_FIX_RESULTS.md`

### 테스트 결과
- `comparison_phase1_hybrid_voting/` - Phase 1 결과 (33.3%)
- `comparison_fixed_v1/` - Fixed v1 기준 (42.9%)
- `comparison_gpt35_langgraph/` - 최초 baseline (19.0%)

---

## 🎓 교훈

### Lesson 1: 문서만으로는 부족
- 구조적 분석 문서가 정확해 보여도 실제 코드와 다를 수 있음
- 가정이 아닌 실제 실행 결과로 검증 필요

### Lesson 2: 단계적 롤백 전략 중요
- 각 수정을 개별 커밋으로 분리
- 성능 저하 시 즉시 롤백 가능하도록

### Lesson 3: 성능 모니터링 필수
- 각 Phase 후 즉시 전체 테스트 실행
- 조기에 문제 발견하여 시간 절약

---

**체크포인트 저장**: 2025-10-02 05:50
**다음 액션**: Phase 1 롤백 → Phase 2 (Table State) 시작
**목표 유지**: 58.8% Original MACT 수준 달성
