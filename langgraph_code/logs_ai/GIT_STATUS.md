# Git 상태 및 변경사항 기록

## 📍 현재 브랜치 정보
- **현재 브랜치**: `langgraph`
- **최신 커밋**: `4cf0b0d - Complete MACT LangGraph implementation with comprehensive documentation`
- **베이스 브랜치**: `main` (a0c99ec - update batch processing)

## 🔄 변경된 파일 목록

### 수정된 파일 (Modified)
1. **main.py** - 메인 실행 스크립트 대대적 업데이트
   - 새로운 저장 시스템 통합
   - 명령행 인수 추가 (--output_dir, --minimal_output, --legacy_output)
   - JSONL 스트리밍 방식 구현

2. **src/mact_langgraph/nodes/core_nodes.py** - 핵심 노드 로직
   - RunPod vLLM 통합 구현
   - create_llm() 함수 개선 (Cold start 대응)
   - 타임아웃 처리 및 연결 테스트 추가

3. **src/mact_langgraph/nodes/tool_nodes.py** - 도구 노드 개선
   - 코드 실행 안정성 향상
   - 오류 처리 로직 개선

4. **src/mact_langgraph/utils/mmqa_utils.py** - 데이터셋 처리 확장
   - TAT 데이터셋 지원 추가
   - convert_tat_to_mmqa_format() 함수 구현
   - load_dataset_universal() 통합 로더

5. **src/mact_langgraph/utils/table_utils.py** - 테이블 처리 개선
   - exact_match() 함수 숫자 비교 로직 개선
   - 코드 실행 안정성 향상

### 새로 추가된 파일 (Untracked)
1. **src/mact_langgraph/utils/result_utils.py** - 새로운 결과 처리 모듈
   - 대용량 데이터셋 대응 저장 시스템
   - JSONL 스트리밍 구현
   - 종합 메트릭 계산 시스템

2. **WORK_PROGRESS.md** - 작업 진행 상황 문서
3. **TODO.md** - 향후 작업 계획
4. **results.json** - 테스트 결과 파일
5. **test_results/** - 테스트 결과 디렉토리
   - predictions_*.jsonl 파일들
   - metrics_*.json 파일들

## 📊 변경사항 통계
- **수정된 파일**: 5개
- **새로 추가된 파일**: 6개 (디렉토리 제외)
- **총 변경 라인**: 약 1000+ 라인 (추정)

## 🎯 주요 변경 내용 요약

### 1. 저장 시스템 혁신
- 기존 단일 JSON → JSONL + JSON 분리 저장
- 대용량 데이터셋 스트리밍 처리
- 자동 파일명 생성 (타임스탬프 포함)

### 2. LLM 백엔드 확장
- OpenAI API 기존 지원 유지
- RunPod vLLM 완전 통합
- Cold start 대응 및 안정성 향상

### 3. 데이터셋 호환성 확장
- MMQA 데이터셋 기존 지원
- TAT 데이터셋 자동 변환 지원
- 범용 데이터 로더 구현

### 4. 사용성 개선
- 새로운 명령행 옵션 추가
- 실시간 진행률 표시
- 상세한 로깅 시스템

## 📅 커밋 이력
```
4cf0b0d (HEAD -> langgraph) Complete MACT LangGraph implementation with comprehensive documentation
a0c99ec (main) update batch processing
4f59e19 update MACT to handle mmqa dataset
bcefd08 Complete SGLang removal and unified LLM interface implementation
23e7c48 use only openai api for llm calling
```

## 🔄 추천 다음 단계
1. 현재 변경사항 커밋
2. main 브랜치와 비교 검토
3. 필요시 풀 리퀘스트 생성
4. 추가 테스트 및 성능 최적화

---
**기록 일시**: 2025-09-28 11:25:00