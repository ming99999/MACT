# 구조적 문제 수정 계획

**작성일**: 2025-10-02
**현재 상태**: Fixed v1 (42.9% accuracy)
**목표**: Original MACT 수준 (58.8% accuracy)
**성능 격차**: -16%p

---

## 📊 현황 요약

### 성능 비교
| 버전 | 정확도 | 에러율 | 평균 단계 | 모델 |
|------|--------|--------|-----------|------|
| **Original MACT** | **58.8%** (10/17) | 23.5% (4/17) | 2.88 | gpt-3.5-turbo |
| **LangGraph (Fixed v1)** | **42.9%** (9/21) | 0.0% (0/21) | 3.38 | gpt-3.5-turbo |
| **격차** | **-16%p** | -23.5%p | +0.5 | - |

### 발견된 5가지 핵심 구조적 문제

1. **❌ CRITICAL: Missing Majority Voting for Tool Results**
   - 영향: 20-30% 질문
   - 예상 개선: +10-15%p

2. **❌ HIGH: Incorrect Table State Propagation**
   - 영향: 15-20% 질문
   - 예상 개선: +8-12%p

3. **❌ HIGH: Different Action Sampling Strategy**
   - 영향: 10-15% 질문
   - 예상 개선: +5-8%p

4. **❌ MEDIUM: Prompt Format Differences**
   - 영향: 5-10% 질문
   - 예상 개선: +3-5%p

5. **❌ MEDIUM: Missing Pre-Answer Aggregation**
   - 영향: 5-10% 질문
   - 예상 개선: +3-5%p

**총 예상 개선**: +29-45%p (목표 58.8% 달성 가능)

---

## 🎯 수정 우선순위 및 계획

### Phase 1: CRITICAL 수정 (예상 +10-15%p)

#### Issue #1: Majority Voting for Tool Results 복원

**현재 문제**:
```python
# LangGraph (tool_nodes.py)
# 도구 실행 결과만 voting
if successful_results:
    result_counts = Counter(successful_results)
    best_result = result_counts.most_common(1)[0][0]
# LLM 관찰과 결합하지 않음 ❌
```

**Original MACT 방식**:
```python
# agents.py:782-788
new_ob = self.retriever_tool(instruction=argument)
if new_ob != []:
    new_ob = [f'Observation {self.step_n}: {item}' for item in new_ob]
    if not self.long_table and not self.code_as_observation:
        new_ob += all_observations  # LLM 관찰과 결합 ✓
    observation = Counter(new_ob).most_common(1)[0][0]
```

**수정 계획**:
1. `tool_nodes.py`에서 각 도구 함수 수정
2. LLM 생성 관찰 결과를 `state`에 저장
3. 도구 실행 결과와 LLM 관찰을 결합하여 majority voting
4. Fallback 메커니즘 추가 (모든 실행 실패 시 LLM 관찰 사용)

**수정 파일**:
- `src/mact_langgraph/nodes/tool_nodes.py` (retriever_tool_node, operator_tool_node)
- `src/mact_langgraph/state.py` (llm_observations 필드 추가)

**테스트 방법**:
```bash
# 부분 실패 시나리오에서 개선 확인
python main.py --debug --debug_limit 5 \
  --plan_model gpt-3.5-turbo --code_model gpt-3.5-turbo
```

---

### Phase 2: HIGH 우선순위 수정 (예상 +13-20%p)

#### Issue #2: Table State Propagation 수정

**현재 문제**:
```python
# LangGraph에서 마지막 테이블만 사용
table_df_code = tables[-1].df_code  # 단순 선택 ❌
```

**Original MACT 방식**:
```python
# agents.py에서 table_dfs 리스트 유지
self.table_dfs.append(target_df)  # 파생 테이블 추적 ✓
recent_table_df = self.table_dfs[-1]  # 최신 파생 테이블 사용
```

**수정 계획**:
1. `state["recent_table_idx"]` 추가로 활성 테이블 추적
2. Retrieve/Operate 성공 시 새 테이블을 활성으로 설정
3. Calculate/다음 단계에서 활성 테이블 참조
4. 다중 테이블 JOIN 시나리오 처리 개선

**수정 파일**:
- `src/mact_langgraph/state.py` (recent_table_idx 필드 추가)
- `src/mact_langgraph/nodes/tool_nodes.py` (모든 도구에서 활성 테이블 관리)

#### Issue #3: Action Sampling Strategy 수정

**현재 문제**:
```python
# LangGraph에서 순차 호출
for _ in range(plan_sample):
    response = await llm.ainvoke(prompt)  # 독립 호출 ❌
```

**Original MACT 방식**:
```python
# Batch API 사용으로 상관관계 있는 샘플 생성
completions = get_completion(prompt, n=5)  # 배치 생성 ✓
```

**수정 계획**:
1. `core_nodes.py`에서 `ainvoke` 대신 batch API 사용
2. OpenAI API의 `n` 파라미터 활용
3. Consistency reward 계산 개선

**수정 파일**:
- `src/mact_langgraph/nodes/core_nodes.py` (action_planner_node)

---

### Phase 3: MEDIUM 우선순위 수정 (예상 +6-10%p)

#### Issue #4: Prompt Format 개선

**현재 문제**:
```python
# LangGraph - 장황한 프롬프트
REACT_SYSTEM_PROMPT = """You are an expert at answering questions...

IMPORTANT: You MUST use the provided tools...
REQUIRED FORMAT: ...
RULES:
1. ALWAYS start by examining...
2. NEVER use Finish as your first action...
"""  # 너무 많은 지시사항 ❌
```

**Original MACT 방식**:
```python
# 간결하고 task-specific
react_agent_prompt = """Answer the following question about the table...
{task_specific_examples}
Question: {question}
"""  # 간결함 ✓
```

**수정 계획**:
1. REACT 프롬프트를 original MACT 스타일로 단순화
2. Task-specific 예제 강화
3. GPT-3.5-turbo에 최적화된 간결한 형식

**수정 파일**:
- `src/mact_langgraph/utils/prompt_utils.py`

#### Issue #5: Pre-Answer Aggregation 추가

**현재 문제**:
- LangGraph는 항상 최대 단계까지 실행
- 간단한 질문도 불필요하게 복잡하게 처리 ❌

**Original MACT 방식**:
```python
# Step 1에서 조기 합의 확인
if self.use_pre_answer and self.step_n == 1:
    early_answers = [extract_answer(obs) for obs in all_observations]
    if has_consensus(early_answers):
        return early_answers[0]  # 조기 종료 ✓
```

**수정 계획**:
1. `answer_generator_node`에서 Step 1 후 조기 합의 확인
2. 간단한 lookup 질문에서 불필요한 단계 방지
3. `use_pre_answer` 설정 활용

**수정 파일**:
- `src/mact_langgraph/nodes/core_nodes.py` (answer_generator_node)

---

## 📅 실행 계획

### Week 1: Phase 1 (CRITICAL)
- **Day 1-2**: Issue #1 수정 (Majority Voting)
  - LLM 관찰 저장 로직 추가
  - 하이브리드 voting 구현
  - Fallback 메커니즘 추가
- **Day 3**: 테스트 및 검증
  - 부분 실패 시나리오 테스트
  - 정확도 측정 (예상: 42.9% → 53-58%)

### Week 2: Phase 2 (HIGH)
- **Day 1-2**: Issue #2 수정 (Table State)
  - recent_table_idx 추가
  - 활성 테이블 추적 로직
  - 다중 단계 시나리오 테스트
- **Day 3**: Issue #3 수정 (Sampling)
  - Batch API 통합
  - Consistency reward 개선
- **Day 4**: 통합 테스트
  - 전체 데이터셋 실행
  - 정확도 측정 (예상: 58% → 63-68%)

### Week 3: Phase 3 (MEDIUM) + 최적화
- **Day 1**: Issue #4 수정 (Prompts)
  - 프롬프트 단순화
  - Task-specific 예제 개선
- **Day 2**: Issue #5 수정 (Pre-Answer)
  - 조기 합의 로직 추가
  - 간단한 질문 최적화
- **Day 3-4**: 전체 테스트 및 미세 조정
  - 전체 MMQA 데이터셋
  - TAT-QA 데이터셋 (가능 시)
  - 최종 정확도 목표: **58-65%**

---

## 🎯 성공 기준

### Phase 1 완료 후
- ✅ 정확도 > 53% (현재 42.9% 대비 +10%p)
- ✅ 에러율 < 5%
- ✅ 부분 실패 시 fallback 작동

### Phase 2 완료 후
- ✅ 정확도 > 60% (원본 58.8% 초과)
- ✅ 다중 단계 질문 정확도 > 50%
- ✅ Department/City/Student 모든 카테고리 > 50%

### Phase 3 완료 후
- ✅ 정확도 > 63% (목표 초과)
- ✅ 평균 단계 수 < 3.0 (효율성 개선)
- ✅ "Unable to determine" < 5%

---

## 🔍 검증 방법

### 각 Phase 후 실행
```bash
# 전체 비교 테스트
python main.py \
  --dataset_path ../datasets_examples/mmqa_samples.json \
  --plan_model gpt-3.5-turbo \
  --code_model gpt-3.5-turbo \
  --plan_sample 3 --code_sample 3 \
  --output_dir comparison_phase{N} \
  --legacy_output

# 원본 MACT와 비교
python ../code/tqa_mmqa.py \
  --dataset_path ../datasets_examples/mmqa_samples.json \
  --plan_model gpt-3.5-turbo \
  --code_model gpt-3.5-turbo \
  --output_dir comparison_original_mact
```

### 성능 메트릭 추적
- 정확도 (전체 및 카테고리별)
- 에러율
- "Unable to determine" 비율
- 평균 단계 수
- 실행 시간

---

## 📊 예상 결과

| Phase | 수정 내용 | 예상 정확도 | 누적 개선 |
|-------|-----------|-------------|-----------|
| **Current** | Fixed v1 | 42.9% | - |
| **Phase 1** | Majority Voting | 53-58% | +10-15%p |
| **Phase 2** | Table State + Sampling | 60-68% | +17-25%p |
| **Phase 3** | Prompts + Pre-Answer | 63-70% | +20-27%p |

---

## 🚨 리스크 및 완화 방안

### Risk 1: Phase 1 수정이 다른 부분에 영향
- **확률**: Medium
- **완화**: 각 수정 후 회귀 테스트, 단계별 커밋

### Risk 2: Batch API 통합 복잡도
- **확률**: Low
- **완화**: OpenAI Python SDK의 기본 지원 활용

### Risk 3: 시간 초과
- **확률**: Low
- **완화**: Phase 1만 완료해도 목표 달성 가능 (53-58%)

---

## 📝 다음 단계

1. ✅ 구조적 분석 완료
2. ✅ 수정 계획 수립
3. ⏭️ **Phase 1 수정 시작**: Issue #1 (Majority Voting)
4. ⏭️ 테스트 및 검증
5. ⏭️ Phase 2, 3 순차 진행

---

**문서 작성 완료**: 2025-10-02
**다음 작업**: Phase 1 구현 시작
**예상 소요**: 2-3주 (aggressive schedule)
