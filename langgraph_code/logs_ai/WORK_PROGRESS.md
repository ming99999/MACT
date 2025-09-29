# MACT LangGraph 구현 진행 상황

## 📊 전체 진행률: 90% 완료

### ✅ 완료된 작업들

#### 1. 기본 아키텍처 구현 (100% 완료)
- **LangGraph 상태 그래프 구조** 설계 및 구현
- **MACTState** 상태 관리 시스템 구현
- **노드 기반 워크플로우** (Planner → Action Selector → Tool Execution → Observer → Termination Checker)
- **비동기 처리** 지원

#### 2. 핵심 노드 구현 (100% 완료)
- **core_nodes.py**: 메인 추론 워크플로우
  - input_processor_node: 입력 데이터 처리
  - planner_node: 후보 액션 생성
  - action_selector_node: 리워드 기반 액션 선택
  - observer_node: 도구 실행 결과 처리
  - termination_checker_node: 종료 조건 확인
  - answer_aggregator_node: 최종 답변 집계

- **tool_nodes.py**: 전문 도구 노드들
  - retriever_tool_node: 테이블 데이터 검색
  - calculator_tool_node: 수학적 계산
  - search_tool_node: Wikipedia 외부 검색
  - operator_tool_node: 복잡한 테이블 연산

#### 3. LLM 통합 시스템 (100% 완료)
- **OpenAI API** 완전 지원
- **RunPod vLLM** 통합 구현
  - Cold start 대응 (300초 타임아웃)
  - Qwen/Qwen3-8B 모델 지원
  - 연결 테스트 및 오류 처리
  - 폴백 로직 제거 (사용자 요청에 따라)

#### 4. 데이터셋 호환성 (100% 완료)
- **MMQA 데이터셋** 완전 지원
- **TAT 데이터셋** 자동 변환 지원
  - convert_tat_to_mmqa_format() 구현
  - load_dataset_universal() 통합 로더
  - 자동 포맷 감지 및 변환

#### 5. 개선된 저장 시스템 (100% 완료)
- **대용량 데이터셋 대응**
  - JSONL 스트리밍 방식 구현
  - 각 아이템 처리 후 즉시 저장
  - 메모리 효율적 처리

- **답변 로그와 메트릭 분리**
  - `predictions_{모델}_{데이터셋}_{타임스탬프}.jsonl`: 상세 응답 로그
  - `metrics_{모델}_{데이터셋}_{타임스탬프}.json`: 종합 평가 메트릭
  - TAT 스타일 호환성 (`pred_answer`, `gold_answer`)

- **자동 파일명 구분**
  - 모델명, 데이터셋명, 타임스탬프 기반
  - 실험 추적 및 관리 용이성

#### 6. 유틸리티 시스템 (100% 완료)
- **prompt_utils.py**: ReAct 프롬프트 생성
- **action_utils.py**: 액션 파싱 및 처리
- **table_utils.py**: 테이블 조작 및 코드 실행
- **result_utils.py**: 결과 저장 및 메트릭 계산
- **mmqa_utils.py**: 데이터셋 로딩 및 변환

#### 7. 테스트 및 검증 (100% 완료)
- **MMQA 데이터셋 테스트**: ✅ 정상 동작 확인
- **TAT 데이터셋 테스트**: ✅ 자동 변환 및 처리 확인
- **OpenAI API 테스트**: ✅ gpt-3.5-turbo 모델 동작 확인
- **저장 시스템 테스트**: ✅ JSONL/JSON 파일 생성 확인

### 📁 핵심 파일 구조

```
src/mact_langgraph/
├── __init__.py           # 패키지 초기화
├── state.py              # 상태 관리 시스템
├── graph.py              # LangGraph 그래프 정의
├── nodes/
│   ├── core_nodes.py     # 메인 추론 노드들
│   └── tool_nodes.py     # 전문 도구 노드들
└── utils/
    ├── prompt_utils.py   # 프롬프트 생성
    ├── action_utils.py   # 액션 처리
    ├── table_utils.py    # 테이블 조작
    ├── result_utils.py   # 결과 저장 (신규)
    └── mmqa_utils.py     # 데이터셋 처리

main.py                   # 메인 실행 스크립트 (업데이트됨)
requirements.txt          # 의존성 패키지
```

### 🔧 새로운 기능들

#### 명령행 인터페이스
```bash
python main.py \
  --dataset_path ../datasets_examples/mmqa_samples.json \
  --output_dir results \          # 결과 디렉토리 지정
  --minimal_output \             # 대용량 데이터셋용 로그 최소화
  --legacy_output \              # 기존 JSON 형식도 함께 저장
  --plan_model gpt-3.5-turbo \   # 계획 모델
  --code_model gpt-3.5-turbo \   # 코드 생성 모델
  --reward_type consistency \    # 리워드 함수 타입
  --debug --debug_limit 1
```

#### 저장 형식 예시

**JSONL 예측 파일**:
```json
{
  "id": 0,
  "question": "질문 내용",
  "predicted": "예측 답변",
  "target": "정답",
  "pred_answer": "예측 답변", // TAT 호환
  "gold_answer": "정답",      // TAT 호환
  "confidence": 0.8,
  "execution_time": 3.79,
  "model_info": {"plan_model": "gpt-3.5-turbo", ...}
}
```

### 🎯 검증된 기능

1. **기존 MACT 모듈 완전 대체**: ✅
2. **TAT 데이터셋 호환성**: ✅
3. **RunPod vLLM 통합**: ✅
4. **대용량 데이터셋 처리**: ✅
5. **유연한 메트릭 평가**: ✅

### 📈 성능 개선사항

- **메모리 효율성**: JSONL 스트리밍으로 대용량 데이터셋 처리 가능
- **확장성**: 새로운 도구 노드 쉽게 추가 가능
- **유연성**: 다양한 LLM 백엔드 지원 (OpenAI, RunPod vLLM)
- **호환성**: TAT 등 다양한 데이터셋 형식 지원
- **추적성**: 자동 파일명 생성으로 실험 관리 용이

---

### 🧪 최신 테스트 결과 (2025-09-28)

#### QWEN3-8B RunPod vLLM 테스트
- **모델**: Qwen/Qwen3-8B via RunPod vLLM
- **데이터셋**: MMQA 21개 문항
- **연결 상태**: ✅ 정상 연결 및 응답 확인
- **성능 문제**: 🐌 매우 느린 속도 (각 문항당 10-20분 소요)

#### 주요 성능 이슈 분석
1. **코드 생성 품질 문제**
   - QWEN3-8B가 매우 verbose한 주석과 설명 생성
   - `unterminated string literal` 등 문법 오류 빈발
   - 각 오류마다 5회씩 재시도 (plan_sample=5, code_sample=5)

2. **과도한 LLM 호출**
   - 단일 문제당 10-20번의 독립적인 API 호출
   - 계획 → 코드 → 오류 → 재시도 → 재시도...
   - 기존 MACT 대비 10-20배 느린 속도

3. **LangGraph 오버헤드**
   - 그래프 노드 간 상태 전환 비용
   - 각 단계별 검증 및 로깅 오버헤드
   - 복잡한 상태 관리

#### 테스트 현황
- **GPT-4o-mini**: 정상 작동하지만 정확도 이슈
- **QWEN3-8B**: 연결 성공, 속도 문제 심각
- **이전 잘못된 모델명**: `Qwen/Qwen2.5-8B` → `Qwen/Qwen3-8B`로 수정

---

**마지막 업데이트**: 2025-09-28 18:25:00
**현재 상태**: 메인 구현 완료, 성능 최적화 필요