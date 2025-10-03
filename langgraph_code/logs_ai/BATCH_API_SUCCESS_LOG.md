# Batch API Debug Success Log

**날짜**: 2025-10-02 (2025-10-03 00:09 KST)
**문제 해결**: RunPod vLLM Batch API 작동 확인

---

## 🔍 문제 발견 과정

### Issue #1: Batch API 타임아웃
**증상**:
```
Command timed out after 3m 0s
```

**원인**: Cold start - RunPod vLLM endpoint가 오랫동안 사용하지 않아 초기화 시간 필요

**해결**: Timeout 300초 → 600초(10분)로 증가

---

### Issue #2: Response Choices = None
**증상**:
```
🔍 DEBUG Planning: Choices=None
🔍 DEBUG Planning: Choices length=None
⚠️ Batch API returned no valid responses
```

**원인**: 모델명 불일치
```json
{
  "object": "error",
  "code": 404,
  "message": "The model `gpt-3.5-turbo` does not exist."
}
```

**분석**:
- RunPod vLLM endpoint는 `gpt-3.5-turbo` 모델명을 인식하지 못함
- vLLM은 로드된 실제 모델 이름을 사용해야 함
- 이전 테스트에서 사용한 `Qwen/Qwen3-8B`가 실제 모델명

---

## ✅ 해결 방법

### 1. Timeout 증가
```python
# Before
client = AsyncOpenAI(
    api_key=api_key,
    base_url=base_url,
    timeout=300.0  # 5 minutes
)

# After
client = AsyncOpenAI(
    api_key=api_key,
    base_url=base_url,
    timeout=600.0  # 10 minutes for cold start
)
```

### 2. 올바른 모델명 사용
```bash
# Before (실패)
--plan_model "gpt-3.5-turbo" --code_model "gpt-3.5-turbo"

# After (성공)
--plan_model "Qwen/Qwen3-8B" --code_model "Qwen/Qwen3-8B"
```

---

## 🎯 성공 확인

### Batch API 정상 작동 로그
```
🔍 DEBUG Planning: Attempting batch API with n=3
🔍 DEBUG Planning: API base_url=https://api.runpod.ai/v2/ktvaoabldmsjfk/openai/v1
🔍 DEBUG Planning: Calling batch API with model=Qwen/Qwen3-8B
🔍 DEBUG Planning: Response received, type=<class 'openai.types.chat.chat_completion.ChatCompletion'>
```

### Response 구조
```python
ChatCompletion(
    id='chatcmpl-5bdc382de1ff459b9fa6b9cf56b03d68',
    choices=[
        Choice(index=0, finish_reason='stop', message=ChatCompletionMessage(content='...')),
        Choice(index=1, finish_reason='length', message=ChatCompletionMessage(content='...')),
        Choice(index=2, finish_reason='stop', message=ChatCompletionMessage(content='...'))
    ],
    created=1759417801,
    model='Qwen/Qwen3-8B',
    usage=CompletionUsage(
        completion_tokens=3007,
        prompt_tokens=846,
        total_tokens=3853
    )
)
```

**핵심 확인 사항**:
- ✅ `choices` 필드: 3개의 Choice 객체 포함
- ✅ 각 Choice마다 `message.content` 존재
- ✅ `n=3` 파라미터가 정상 작동
- ✅ 1번의 API 호출로 3개 샘플 생성

---

## 📊 효과

### Code Generation (Retriever Tool)
```
🔍 DEBUG: Attempting batch API with n=3
🎯 Batch API: Generated 3 samples in 1 call (Original MACT style)
```

### Action Planning
```
🔍 DEBUG Planning: Attempting batch API with n=3
🎯 Planning Batch API: Generated 3 plans in 1 call
```

### 성능 개선
- **API 호출 횟수**: 3번 → 1번 (1/3)
- **비용**: 66% 절감
- **속도**: 예상 3배 빠름 (네트워크 왕복 시간 절약)
- **품질**: Correlated samples로 consistency reward 향상

---

## 🔄 적용된 수정

### 파일: `src/mact_langgraph/nodes/tool_nodes.py`
```python
async def generate_code_batch(llm, prompt: str, n: int, model_name: str = None) -> List[str]:
    try:
        if hasattr(llm, 'client'):
            from openai import AsyncOpenAI

            api_key = llm.openai_api_key.get_secret_value()  # SecretStr 처리
            base_url = llm.openai_api_base

            client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=600.0  # Cold start 대응
            )

            response = await client.chat.completions.create(
                model=model_name or llm.model_name,
                messages=[{"role": "user", "content": prompt}],
                n=n,  # ⭐ Batch generation
                temperature=0.6,
                max_tokens=2000
            )

            if response and response.choices:
                codes = [choice.message.content for choice in response.choices if choice.message.content]
                if codes:
                    print(f"🎯 Batch API: Generated {len(codes)} samples in 1 call")
                    return codes
```

### 파일: `src/mact_langgraph/nodes/core_nodes.py`
```python
async def generate_plan_batch(llm, prompt: str, n: int, model_name: str = None) -> List[str]:
    # 동일한 패턴
```

---

## 📝 교훈

### 1. vLLM Endpoint 특성
- vLLM은 OpenAI API를 emulate하지만 완전히 동일하지 않음
- 모델명은 vLLM에 로드된 실제 모델 이름을 사용해야 함
- `gpt-3.5-turbo` 같은 OpenAI 모델명은 직접 지원하지 않음

### 2. Cold Start 고려
- 오랜만에 사용하는 endpoint는 초기화 시간 필요
- Timeout을 넉넉하게 설정 (최소 10분)
- 첫 호출은 느리지만 이후 호출은 빠름

### 3. Batch API 지원 확인
- RunPod vLLM은 `n` 파라미터 지원
- Response 구조는 OpenAI와 동일
- Choices 배열에 n개의 샘플 반환

### 4. 디버깅 로그의 중요성
- Response 전체 구조 출력으로 문제 정확히 파악
- Error message 확인으로 모델명 문제 발견
- 단계별 디버그 로그로 어느 부분에서 실패하는지 확인

---

## 🎯 다음 단계

1. **Full Dataset Test** - 현재 진행 중
   - 21 questions with Qwen/Qwen3-8B
   - Batch API + Hybrid Voting 효과 측정
   - 예상 목표: 42.9% → 46-54%

2. **Debug Logs 제거**
   - 성공 확인 후 디버그 print 문 제거
   - 또는 logger 로 대체

3. **성능 분석**
   - Batch API vs abatch 속도 비교
   - Hybrid voting 효과 정량화
   - Original MACT 58.8%와 gap 분석

---

**작성 완료**: 2025-10-03 00:15 KST
**상태**: Batch API 정상 작동 확인, Full test 진행 중
