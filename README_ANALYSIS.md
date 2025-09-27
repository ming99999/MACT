# MACT 프로젝트 분석 보고서

## 1. 프로젝트 개요

**MACT (Multi-Agent Collaboration with Tool Use)** 는 복잡한 테이블 질의응답을 위한 효율적인 멀티 에이전트 협업 프레임워크입니다. NAACL 2025에 발표된 연구 프로젝트로, 온라인 계획과 도구 사용을 통한 테이블 질의응답 성능 향상을 목표로 합니다.

### 주요 특징
- 멀티 에이전트 협업 기반 테이블 질의응답
- ReAct (Reasoning and Acting) 패러다임 적용
- 다양한 테이블 QA 데이터셋 지원 (WTQ, TAT, CRT, SciTab, DataBench, MMQA)
- GPT 모델과 오픈소스 모델 통합 지원
- Tree-of-Thought (ToT) 기반 행동 선택

## 2. 프로젝트 구조

```
MACT/
├── code/                          # 메인 소스 코드
│   ├── tqa.py                     # 메인 실행 스크립트
│   ├── agents.py                  # ReactAgent 클래스 정의
│   ├── llm.py                     # 통합 LLM 인터페이스
│   ├── config.py                  # LLM 클라이언트 설정
│   ├── tot.py                     # Tree-of-Thought 구현
│   ├── utils.py                   # 유틸리티 함수들
│   ├── prompts_table.py           # 프롬프트 템플릿
│   ├── fewshots_table.py          # Few-shot 예제
│   ├── tqa_batch.py               # 배치 처리
│   ├── tqa_mmqa.py                # MMQA 데이터셋 처리
│   └── test_unified_llm.py        # LLM 테스트
├── datasets_examples/             # 데이터셋 예제
│   ├── tat.jsonl                  # TAT 데이터셋 예제
│   ├── mmqa_samples.json          # MMQA 데이터셋 예제
│   └── databench_table/           # DataBench 테이블 데이터
├── requirements.txt               # Python 의존성
├── .env.template                  # 환경 변수 템플릿
└── README.md                      # 프로젝트 문서
```

## 3. 주요 모듈 및 클래스

### 3.1 ReactAgent (agents.py)
**핵심 에이전트 클래스**
- **역할**: 테이블 질의응답을 위한 추론 및 행동 수행
- **주요 기능**:
  - `run()`: 에이전트 실행 메인 루프
  - `step()`: 한 스텝씩 추론-행동-관찰 수행
  - `retriever_tool()`: 테이블 검색 도구
  - `calculator_tool()`: 계산 도구
  - `numerical_tool()`: 수치 연산 도구

**주요 속성**:
- `question`: 질문 텍스트
- `table_string`: 테이블 데이터 (문자열 형태)
- `table_df`: 테이블 데이터 (Pandas DataFrame 코드)
- `scratchpad`: 추론 과정 기록
- `max_steps`: 최대 스텝 수

### 3.2 UnifiedLLM (llm.py)
**통합 LLM 인터페이스**
- **역할**: GPT 모델과 오픈소스 모델 통합 관리
- **주요 기능**:
  - `__call__()`: 텍스트 생성 메인 메서드
  - `generate_batch()`: 배치 생성 (비동기)
  - `get_completion()`: 기존 호환성을 위한 메서드

**지원 모델**:
- GPT 모델: gpt-3.5-turbo, gpt-4, gpt-4-turbo
- 오픈소스 모델: Qwen, Llama, Mistral, Phi, CodeLlama

### 3.3 LLMConfig (config.py)
**LLM 클라이언트 설정 관리**
- **역할**: 모델별 적절한 클라이언트 라우팅
- **주요 기능**:
  - `get_client_for_model()`: 모델에 따른 클라이언트 반환
  - `is_gpt_model()`: GPT 모델 여부 판단
  - `is_open_source_model()`: 오픈소스 모델 여부 판단

## 4. 핵심 알고리즘 및 워크플로우

### 4.1 ReAct 패러다임
MACT는 ReAct (Reasoning and Acting) 패러다임을 기반으로 합니다:

1. **Thought**: 현재 상황에 대한 추론
2. **Action**: 수행할 행동 결정 (Retrieve, Calculate, Search, Finish)
3. **Observation**: 행동 결과 관찰

### 4.2 주요 워크플로우

```
1. 데이터셋 로드 (JSONL 형태)
   ↓
2. ReactAgent 인스턴스 생성
   ↓
3. 에이전트 실행 루프:
   a. 프롬프트 생성 (plan_sample 개수만큼)
   b. LLM으로부터 후보 행동 생성
   c. 보상 함수로 최적 행동 선택
   d. 선택된 행동 실행
   e. 관찰 결과를 스크래치패드에 기록
   ↓
4. 최종 답안 도출 및 저장
```

### 4.3 행동 유형
- **Retrieve[instruction]**: 테이블에서 정보 검색
- **Calculate[equation]**: 수식 계산
- **Search[query]**: Wikipedia 검색
- **Operate[instruction]**: 테이블 연산 수행
- **Finish[answer]**: 최종 답안 제출

### 4.4 보상 함수 (Reward Functions)
다양한 보상 함수를 통해 최적 행동 선택:
- **consistency**: 다수결 기반 선택
- **llm**: LLM 기반 평가
- **logp**: 로그 확률 기반
- **rollout**: 롤아웃 기반
- **combined**: 복합 방법

## 5. 지원 데이터셋

### 5.1 테이블 QA 데이터셋
- **WTQ** (WikiTableQuestions): Wikipedia 테이블 질의응답
- **TAT** (TAT-QA): 하이브리드 수치적/기호적 추론
- **CRT** (Complex Reasoning over Tables): 복잡한 테이블 추론
- **SciTab**: 과학 도메인 테이블 질의응답
- **DataBench**: 데이터 분석 벤치마크
- **MMQA**: 멀티모달 질의응답

### 5.2 데이터 형식
각 데이터 인스턴스는 다음 필드를 포함:
```json
{
  "statement": "질문 또는 진술 (문자열)",
  "table_text": "테이블 데이터 (리스트 형태)",
  "answer": "정답 (리스트 형태)"
}
```

## 6. 의존성 및 요구사항

### 6.1 Python 패키지 (requirements.txt)
**핵심 라이브러리**:
- `openai==1.55.3`: OpenAI API 클라이언트
- `pandas==2.2.2`: 데이터 처리
- `langchain==0.2.1`: LLM 애플리케이션 프레임워크
- `transformers==4.44.1`: 허깅페이스 트랜스포머
- `python-dotenv==1.0.0`: 환경 변수 관리

**기타 라이브러리**:
- `accelerate`, `datasets`, `numpy`, `scipy`
- `pandasql`: SQL 쿼리 지원
- `wikipedia`: Wikipedia 검색
- `nltk`, `tqdm`: 자연어 처리 및 진행률 표시

### 6.2 환경 설정
**.env 파일 설정**:
```bash
# OpenAI 설정 (GPT 모델용)
OPENAI_API_KEY=your_openai_api_key

# RunPod 설정 (오픈소스 모델용)
RUNPOD_API_KEY=your_runpod_api_key
RUNPOD_BASE_URL=your_runpod_vllm_endpoint
```

## 7. 주요 기능별 상세 분석

### 7.1 멀티 에이전트 협업
- **계획 모델**과 **코드 모델**을 분리하여 전문화
- 다양한 모델 조합 지원 (GPT + 오픈소스 혼합 가능)
- 샘플링 기반 후보 생성 및 최적 선택

### 7.2 도구 사용 (Tool Use)
**테이블 조작 도구**:
- Pandas 기반 테이블 연산
- SQL 쿼리 실행
- 수치 계산 및 통계 분석

**외부 지식 접근**:
- Wikipedia 검색 통합
- 컨텍스트 정보 활용

### 7.3 온라인 계획 (Online Planning)
- 단계별 동적 계획 수립
- 이전 관찰 결과를 바탕으로 다음 행동 결정
- 실패 시 재시도 및 경로 수정

### 7.4 평가 및 메트릭
- **Exact Match (EM)**: 정확한 일치 평가
- 정규화된 답안 비교 (소문자, 구두점 제거 등)
- 데이터셋별 특화 평가 스크립트 지원

## 8. 사용법 및 실행 예제

### 8.1 기본 실행
```bash
# GPT 모델 사용
python code/tqa.py \
  --plan_model_name gpt-3.5-turbo \
  --code_model_name gpt-3.5-turbo \
  --dataset_path datasets_examples/tat.jsonl \
  --task tat

# 오픈소스 모델 사용
python code/tqa.py \
  --plan_model_name Qwen/Qwen3-8B \
  --code_model_name Qwen/Qwen3-8B \
  --dataset_path datasets_examples/tat.jsonl \
  --task tat
```

### 8.2 주요 매개변수
- `--plan_sample`: 계획 후보 생성 개수 (기본값: 5)
- `--code_sample`: 코드 실행 시도 횟수 (기본값: 5)
- `--max_step`: 최대 추론 단계 (기본값: 6)
- `--as_reward`: 보상 함수 유형 (consistency, llm, logp, etc.)

## 9. 확장성 및 커스터마이징

### 9.1 새로운 데이터셋 추가
1. 데이터 형식을 MACT 표준에 맞게 변환
2. `agents.py`에서 새 태스크 유형 추가
3. 해당하는 프롬프트 및 예제 작성

### 9.2 새로운 모델 통합
1. `config.py`에서 모델 패턴 추가
2. 필요시 `llm.py`에서 특화 처리 로직 구현
3. 환경 변수에 API 설정 추가

### 9.3 새로운 도구 추가
1. `agents.py`의 `ReactAgent`에 새 도구 메서드 추가
2. `parse_action()` 함수에서 새 액션 타입 지원
3. 해당하는 프롬프트에 도구 설명 추가

## 10. 성능 및 최적화

### 10.1 효율성 개선
- 통합 LLM 인터페이스로 모델 관리 단순화
- 비동기 배치 처리 지원
- 토큰 사용량 추정 및 모니터링

### 10.2 정확도 향상
- 다양한 보상 함수를 통한 행동 선택 최적화
- Few-shot 예제를 통한 컨텍스트 학습
- 다단계 추론을 통한 복잡한 문제 해결

## 11. 한계 및 향후 개선 방향

### 11.1 현재 한계
- 긴 테이블 처리 시 성능 저하 가능
- 복잡한 다단계 추론에서 오류 누적
- 모델별 최적화 부족

### 11.2 향후 개선 방향
- 적응형 테이블 축약 기법 개발
- 더 정교한 오류 복구 메커니즘
- 도메인별 특화 모델 통합
- 더 효율적인 계획 알고리즘 개발

---

이 분석 보고서는 MACT 프로젝트의 전반적인 구조와 기능을 종합적으로 정리한 것입니다. 각 모듈의 상세한 구현은 해당 소스 코드를 직접 참조하시기 바랍니다.