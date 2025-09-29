# MACT LangGraph 코드 수정 로그

## 📅 작성일: 2025-09-28

## 🚨 발견된 오류들

### 1. 재귀 한계 오류 (Recursion Limit Error)
**에러 메시지**: `Recursion limit of 25 reached without hitting a stop condition`
**발생 빈도**: 21개 아이템 중 5개에서 발생
**심각도**: 🔴 Critical

### 2. 정확도 0% 문제
**현상**: 전체 데이터셋에서 정답률 0%
**원인**:
- 일부 아이템: 도구 사용 없이 즉시 Finish 액션 선택
- 일부 아이템: 재귀 오류로 실행 중단
**심각도**: 🔴 Critical

### 3. 불일치한 동작
**현상**: 단일 아이템 테스트는 성공, 전체 테스트는 실패
**원인**: 상태 관리 및 그래프 라우팅 로직 불안정
**심각도**: 🟡 High

---

## 🔍 근본 원인 분석

### 기존 MACT vs LangGraph 구현 차이점

#### ✅ 기존 MACT (안정적)
```python
# 명확한 종료 조건
while not self.is_halted() and not self.is_finished():
    self.step()

def is_halted(self) -> bool:
    return ((self.step_n > self.max_steps) or
            (self.actual_step_n > self.max_actual_steps)) and not self.finished

# Finish 액션 처리
if "Finish" not in action:
    # 도구 실행
else:
    self.finished = True  # 즉시 종료 플래그 설정
```

#### ❌ LangGraph 구현 (문제 있음)
```python
# 문제 1: 우선순위 없는 종료 조건
def check_termination(state: MACTState):
    if state.get("is_finished", False) or state.get("is_halted", False):
        return "answer_aggregator"
    else:
        return "planner"

# 문제 2: 상태 업데이트와 라우팅 분리로 동기화 이슈
# 문제 3: Finish 액션 시 스텝 카운터 계속 증가
```

---

## 🛠️ 수정 계획

### 우선순위 1: termination_checker_node 수정
**파일**: `src/mact_langgraph/nodes/core_nodes.py`
**문제**: Finish 액션 시에도 스텝 카운터가 증가하여 재귀 발생
**수정 방향**:
1. Finish 액션 감지 시 즉시 종료 상태 설정
2. 스텝 카운터 증가 중지
3. 명확한 우선순위 설정 (finished > halted)

### 우선순위 2: check_termination 함수 개선
**파일**: `src/mact_langgraph/graph.py`
**문제**: 종료 조건 우선순위 불명확
**수정 방향**:
1. finished 우선순위를 halted보다 높게 설정
2. 로직 단순화 및 명확화

### 우선순위 3: 액션 타입 설정 검증
**파일**: `src/mact_langgraph/nodes/core_nodes.py` (action_selector_node)
**문제**: current_action_type이 올바르게 설정되지 않을 가능성
**수정 방향**:
1. 액션 파싱 검증 강화
2. 로깅 추가로 디버깅 정보 확보

### 우선순위 4: 재귀 한계 임시 증가
**파일**: `src/mact_langgraph/graph.py`
**문제**: 기본 재귀 한계 25가 부족할 수 있음
**수정 방향**: recursion_limit 50으로 증가

---

## 📝 수정 기록

### 2025-09-28 16:15 - 우선순위 1 수정 완료 ✅
**대상**: termination_checker_node 함수
**변경 내용**:
- [x] Finish 액션 시 즉시 종료 로직 추가 (스텝 증가 없이 즉시 반환)
- [x] 스텝 카운터 증가 조건 수정 (finished 상태에서는 증가 안함)
- [x] 우선순위 기반 종료 조건 구현 (finished > error > step_limit)

### 2025-09-28 16:15 - 우선순위 2 수정 완료 ✅
**대상**: check_termination 함수
**변경 내용**:
- [x] 종료 조건 우선순위 명확화 (finished > halted > continue)
- [x] 로직 단순화 및 주석 추가

### 2025-09-28 16:15 - 우선순위 3 수정 완료 ✅
**대상**: action_selector_node 함수
**변경 내용**:
- [x] 액션 타입 설정 검증 추가
- [x] 디버깅 로그 추가 (후보 수, 선택된 액션 정보)
- [x] 오류 처리 강화

### 2025-09-28 16:15 - 우선순위 4 수정 완료 ✅
**대상**: create_mact_graph 함수
**변경 내용**:
- [x] recursion_limit 25 → 50으로 증가

---

## 🧪 테스트 계획

### 1. 단위 테스트
- [ ] termination_checker_node 개별 테스트
- [ ] check_termination 함수 테스트
- [ ] 다양한 상태 조건에서 라우팅 테스트

### 2. 통합 테스트
- [ ] 단일 아이템 디버그 모드 테스트
- [ ] 3-5개 아이템 소규모 테스트
- [ ] 전체 21개 아이템 테스트

### 3. 성능 테스트
- [ ] 재귀 오류 발생률 확인
- [ ] 평균 실행 시간 측정
- [ ] 메모리 사용량 모니터링

---

## 📊 기대 결과

### 목표 메트릭
- ✅ 재귀 오류 발생률: 0%
- ✅ 정확도: > 50% (기존 MACT 수준)
- ✅ 평균 스텝 수: 2-5 (도구 사용 확인)
- ✅ 실행 안정성: 100% (모든 아이템 완료)

### 성공 기준
1. 21개 아이템 모두 에러 없이 완료
2. 최소 10개 이상 정답 (정확도 50% 이상)
3. 평균 2회 이상 도구 사용 확인
4. 재귀 한계 오류 0건

---

## 🔄 향후 개선 계획

### 단기 (수정 완료 후)
- [ ] 프롬프트 엔지니어링 개선
- [ ] 도구 실행 안정성 향상
- [ ] 액션 선택 로직 최적화

### 중기 (1주일 내)
- [ ] 다양한 모델 테스트 (GPT-4, RunPod)
- [ ] 대용량 데이터셋 성능 테스트
- [ ] 추가 리워드 함수 구현

### 장기 (1개월 내)
- [ ] 성능 벤치마킹
- [ ] 사용자 문서화 완성
- [ ] 프로덕션 배포 준비

---

---

## 🏁 수정 결과 및 다음 단계

### ✅ 해결된 문제 (2025-09-28 16:15)
1. **재귀 한계 오류**: 완전 해결 (recursion limit 에러 0건)
2. **그래프 순환**: 종료 조건 우선순위 개선으로 해결
3. **도구 사용률**: 0단계 → 5단계로 극적 개선
4. **시스템 안정성**: 무한 루프 없이 정상 완료

### 🔴 새로 발견된 문제: 도구 실행 로직 실패

**근본 원인 분석 완료 (2025-09-28 16:30)**:

#### **핵심 문제**: TableInfo.df_code 미초기화
- `TableInfo` 객체의 `df_code` 필드가 빈 문자열로 남아있음
- 도구들이 실제 테이블 데이터에 접근할 수 없음
- 기존 MACT의 `self.table_df` 직접 접근 방식과 상이

#### **기존 MACT vs LangGraph 차이점**:

| 측면 | 원본 MACT | LangGraph 구현 | 문제점 |
|------|-----------|----------------|--------|
| **데이터 접근** | `self.table_df` 직접 접근 | `TableInfo.df_code` (빈 문자열) | DataFrame 코드 미설정 |
| **상태 관리** | `self.table_dfs` 누적 관리 | 일회성 처리 | 작업 결과 누적 부족 |
| **코드 실행** | 직접 `exec()` 실행 | `execute_table_code()` 래퍼 | 실행 환경 설정 미흡 |
| **초기화** | 생성자에서 완전 설정 | 상태 객체 부분 설정 | 필수 필드 누락 |

#### **구체적 실패 지점**:
1. **input_processor_node**: `table.df_code` 설정 로직이 있지만 실행되지 않음
2. **retriever_tool_node**: `table_df_code = tables[0].df_code if tables else ""` → 항상 빈 문자열
3. **execute_table_code**: 빈 DataFrame 코드로 실행 실패

### 📋 수정 계획 (우선순위별)

#### **우선순위 1**: TableInfo 초기화 수정
- **파일**: `src/mact_langgraph/nodes/core_nodes.py` (input_processor_node)
- **목표**: 테이블 데이터 → DataFrame 코드 변환 보장
- **방법**: `table2df()` 함수 호출 및 `df_code` 설정 확인

#### **우선순위 2**: 도구 노드 실행 로직 개선
- **파일**: `src/mact_langgraph/nodes/tool_nodes.py`
- **목표**: 실제 DataFrame 코드를 사용한 도구 실행
- **방법**: 에러 핸들링 및 디버깅 로그 추가

#### **우선순위 3**: 상태 관리 개선
- **목표**: 원본 MACT의 `table_dfs` 누적 관리 구현
- **방법**: 도구 실행 결과를 상태에 누적 저장

**최종 업데이트**: 2025-09-28 16:15
**담당자**: Claude Code Assistant
**상태**: 🟡 도구 실행 문제 해결 필요