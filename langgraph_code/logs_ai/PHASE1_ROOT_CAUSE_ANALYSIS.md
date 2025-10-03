# Phase 1 성능 저하 근본 원인 분석

**날짜**: 2025-10-02 06:10
**문제**: Phase 1 구현 후 42.9% → 33.3% 성능 저하 (-9.5%p)

---

## 🔍 발견된 핵심 차이점

### Issue #1: LLM 호출 방식의 근본적 차이

#### Original MACT 방식
```python
# agents.py:283 - 한 번의 LLM 호출로 여러 샘플 생성
codes = self.llm(prompt, num_return_sequences=max_attempt, return_prob=False)
# → OpenAI API의 n 파라미터 사용
# → 1번의 API 호출로 5개 샘플 생성 (상관관계 있음)
```

#### LangGraph 방식 (잘못됨)
```python
# tool_nodes.py:125 - 여러 번 독립적으로 호출
responses = await llm.abatch([prompt] * code_sample)
# → 3번의 독립적인 API 호출
# → 각 샘플이 uncorrelated (독립적)
```

**영향**:
- ❌ **비효율**: 3번 vs 1번 API 호출 (3배 느림, 3배 비용)
- ❌ **품질 저하**: Consistency reward가 약화됨
  - Original: 상관관계 있는 샘플들의 majority voting
  - LangGraph: 독립 샘플들의 voting (신뢰도 낮음)

---

### Issue #2: all_observations의 정체

#### Original MACT의 hybrid voting 메커니즘
```python
# agents.py:782-788 - Retrieve tool
new_ob = self.retriever_tool(instruction=argument)  # 도구 실행 결과 리스트
if new_ob != []:
    new_ob = [f'Observation {self.step_n}: {item}' for item in new_ob]

    # ⭐ 핵심: all_observations는 as_reward_fn에서 온다!
    if not self.long_table and not self.code_as_observation:
        new_ob += all_observations  # LLM이 생성한 observations 추가

    observation = Counter(new_ob).most_common(1)[0][0]  # Hybrid voting
```

#### as_reward_fn에서 all_observations 생성
```python
# agents.py:578-590 - as_consistency 함수
def as_consistency(action_thought, observations):
    # observations는 LLM 샘플에서 추출한 관찰들
    target_observation = Counter(observations).most_common(1)[0][0]
    # ...
    return target_thought, target_action, target_observation, observations
    # ⭐ observations를 all_observations로 반환!

# agents.py:754 - step 함수에서 사용
thought, action, observation, all_observations = self.as_reward_fn(sampled)
```

**핵심 발견**:
- `all_observations`는 **LLM 샘플에서 파싱한 Observation들**
- Action planning 단계에서 LLM이 **예측한** observations
- 실제 도구 실행 결과와 **예측된 관찰을 결합**하여 voting

---

### Issue #3: LangGraph Phase 1 구현의 문제

#### 잘못된 구현
```python
# tool_nodes.py:171-175 - Phase 1 시도
if not long_table and not code_as_observation and successful_results:
    # Generate LLM observations from successful results
    for i, result in enumerate(successful_results):
        llm_obs = f"Observation {state['current_step']}: {result[:100]}"
        all_observations.append(llm_obs)
```

**문제점**:
1. ❌ LLM observations를 **도구 결과에서 복사**
   - Original: LLM이 **예측한** observations 사용
   - Phase 1: 도구 결과를 단순 복사 → 중복 카운팅

2. ❌ `all_observations`의 출처가 잘못됨
   - Original: `as_reward_fn`의 action planning에서 생성
   - Phase 1: Tool execution에서 생성 (틀림!)

3. ❌ Observation 중복으로 voting 왜곡
   ```
   Original voting:
   - Tool result: "Treasury, 115897" (3/5 성공)
   - LLM prediction: "Treasury department" (2/5 샘플)
   - Hybrid voting: 5개 관찰 중 majority

   Phase 1 voting (잘못됨):
   - Tool result: "Treasury, 115897" (3/5)
   - Duplicated obs: "Observation: Treasury, 115897" (3/5)
   - Total: 6개 중 3개 중복 → 왜곡!
   ```

---

## 💡 정확한 수정 방안

### Fix #1: Batch API 사용 (num_return_sequences)

**Before (LangGraph - 잘못됨)**:
```python
responses = await llm.abatch([prompt] * code_sample)
```

**After (Original MACT 방식)**:
```python
# OpenAI API의 n 파라미터 사용
response = await llm.ainvoke(
    prompt,
    config={"configurable": {"n": code_sample}}  # 한 번에 여러 샘플
)
# 또는 직접 OpenAI client 사용
from openai import AsyncOpenAI
client = AsyncOpenAI()
response = await client.chat.completions.create(
    model=model_name,
    messages=[{"role": "user", "content": prompt}],
    n=code_sample,  # ⭐ 핵심: 한 번에 여러 샘플
    temperature=0.6
)
codes = [choice.message.content for choice in response.choices]
```

---

### Fix #2: all_observations를 action planning에서 생성

**Step 1: Action planner에서 observations 추출**
```python
# core_nodes.py - action_planner_node
async def action_planner_node(state: MACTState) -> MACTState:
    # ... action planning ...

    # ⭐ LLM 샘플에서 observations 파싱
    llm_observations = []
    for sample in raw_llm_responses:
        # "Observation N: ..." 패턴 추출
        obs_pattern = rf"Observation {state['current_step']}:(.*?)(?:Thought {state['current_step']+1}:|$)"
        match = re.search(obs_pattern, sample, re.DOTALL)
        if match:
            obs = f"Observation {state['current_step']}: {match.group(1).strip()}"
            llm_observations.append(obs)

    # State에 저장
    return {
        **state,
        "llm_observations": llm_observations,  # 예측된 observations
        # ...
    }
```

**Step 2: Tool execution에서 hybrid voting**
```python
# tool_nodes.py - retriever_tool_node
async def retriever_tool_node(state: MACTState) -> MACTState:
    # ... tool execution ...

    # 도구 실행 결과
    tool_results = [...]  # successful_results

    # ⭐ Original MACT 방식 hybrid voting
    new_ob = [f"Observation {state['current_step']}: {res}" for res in tool_results]

    long_table = state.get("long_table_op") not in [None, "ignore"]
    code_as_observation = state.get("code_as_observation", False)

    if not long_table and not code_as_observation:
        # LLM이 예측한 observations 추가
        new_ob += state.get("llm_observations", [])

    # Majority voting
    observation = Counter(new_ob).most_common(1)[0][0]

    return {...}
```

---

### Fix #3: Action planning에서 batch sampling

**Before**:
```python
# core_nodes.py - 순차 호출
for _ in range(plan_sample):
    response = await llm.ainvoke(prompt)
```

**After**:
```python
# Batch API 사용
response = await llm.ainvoke(
    prompt,
    config={"configurable": {"n": plan_sample}}
)
```

---

## 📊 예상 효과

### Fix #1 (Batch API)
- **속도**: 3배 빠름 (1번 vs 3번 호출)
- **비용**: 1/3 절감
- **품질**: Consistency reward 향상
- **예상 개선**: +3-5%p

### Fix #2 (Correct hybrid voting)
- **Voting 정확도**: 왜곡 제거
- **Observation 품질**: 예측 + 실제 결합
- **예상 개선**: +8-12%p

### Fix #3 (Action planning batch)
- **Consistency**: 상관관계 있는 샘플
- **Action selection**: 더 robust한 선택
- **예상 개선**: +2-4%p

**총 예상 개선**: +13-21%p
**목표 정확도**: 33.3% + 13-21% = **46-54%**

---

## 🎯 수정 우선순위

### Phase 1 Revised Plan

1. **Fix #1: Batch API for code generation** (HIGH)
   - 파일: `tool_nodes.py`
   - 영향: 모든 tool nodes (retrieve, operate, calculate)
   - 예상 시간: 2-3시간

2. **Fix #2: LLM observations from action planning** (CRITICAL)
   - 파일: `core_nodes.py`, `tool_nodes.py`
   - 영향: Action planner → tool execution 흐름
   - 예상 시간: 3-4시간

3. **Fix #3: Batch API for action planning** (MEDIUM)
   - 파일: `core_nodes.py`
   - 영향: Action generation
   - 예상 시간: 1-2시간

**총 예상 시간**: 6-9시간 (1일 작업)

---

## ✅ 검증 방법

### Test 1: Batch API 동작 확인
```python
# 1번 호출로 3개 샘플 생성 확인
# 로그에서 API call count 체크
```

### Test 2: LLM observations 확인
```python
# action_planner_node에서 observations 추출 확인
# tool_nodes에서 hybrid voting 확인
# 로그에서 "Hybrid voting: tool + LLM obs" 메시지 확인
```

### Test 3: 성능 측정
```bash
# Quick test (5 questions)
python main.py --debug --debug_limit 5 ...
# Expected: 40-50% accuracy

# Full test (21 questions)
python main.py --dataset_path ...
# Expected: 46-54% accuracy
```

---

**작성 완료**: 2025-10-02 06:10
**다음 작업**: Fix #1, #2, #3 순차 구현
**목표**: 46-54% accuracy (Original MACT 58.8%에 근접)
