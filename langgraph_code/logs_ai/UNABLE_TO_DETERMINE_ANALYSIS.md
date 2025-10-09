# "Unable to determine answer" Root Cause Analysis & Solution

**분석 날짜**: 2025-10-02
**분석자**: Claude Code AI
**심각도**: 🔴 CRITICAL - 3개 질문 실패 원인

---

## 📋 Executive Summary

"Unable to determine answer"가 발생하는 근본 원인은 **컬럼명 불일치**입니다:

1. **table2df()**가 컬럼을 소문자로 normalize (예: `Theme` → `theme`)
2. **LLM**이 질문을 보고 원본 컬럼명으로 코드 생성 (예: `df['Theme']`)
3. **실행 시 KeyError** 발생 → 3번 재시도 모두 실패 → "Unable to perform operation"

---

## 🔍 발견 과정

### 1단계: 실패 케이스 식별

```bash
# 비교 테스트 결과 분석
comparison_fixed_v1/predictions_gpt-3.5-turbo_mmqa_samples_20251001_230038.jsonl

# 발견된 "Unable to determine" 케이스:
- Q12: Official Name of city (MTV Cube theme)
- Q15: Mobile number lookup
- Q16: Email lookup
```

### 2단계: 에러 패턴 확인

**Q12 실행 로그**:
```
Step 1: ✅ 데이터 조회 성공 (competition_id=5, host_city_id=5 확인)
Step 2: ❌ Operation attempt 1 failed: 'theme'
        ❌ Operation attempt 2 failed: 'theme'
        ❌ Operation attempt 3 failed: 'theme'
        → "Unable to perform operation"

Step 3: ❌ Operation attempt 1 failed: 'competition_id'
        ...
```

**Q15 에러**:
```
- 'candidate_id' KeyError (3회)
- 'cell_mobile_number' KeyError (3회)
```

**Q16 에러**:
```
- 'candidate_id' KeyError (3회)
- 'candidate_details' KeyError (3회)
```

### 3단계: 근본 원인 파악

#### table2df()에서 컬럼 normalize:
```python
# table_utils.py:110-111
if normalize_columns:
    header = [normalize_column_name(col) for col in header]
    # 'Theme' → 'theme'
    # 'Host_city_ID' → 'host_city_id'
```

#### LLM이 생성한 코드에서 원본 컬럼명 사용:
```python
# LLM 생성 코드 (실패)
result = df[df['Theme'] == 'MTV Cube']  # KeyError: 'Theme'

# 실제 필요한 코드
result = df[df['theme'] == 'MTV Cube']  # 정상 작동
```

#### 프롬프트에 컬럼 정보 없음:
```python
# build_code_generation_prompt() - 수정 전
f"""Generate Python code to: {instruction}

Table setup:
{table_df_code}  # 컬럼 리스트 없음!

Requirements:
- Use pandas operations
- ...
```

---

## 💡 해결 방안

### Solution 1: table2df()에 컬럼 리스트 추가 ✅

**파일**: `src/mact_langgraph/utils/table_utils.py:146-149`

```python
output += "df=pd.DataFrame(data)\n"

# 🎯 Add column list as comment to help LLM generate correct code
output += f"# Available columns: {', '.join(header)}\n"

return output
```

**효과**:
```python
# 생성된 df_code
import pandas as pd
data={'competition_id':[1, 5],'year':[2013, 2003],'theme':['Carnival M', 'MTV Cube']}
df=pd.DataFrame(data)
# Available columns: competition_id, year, theme, host_city_id, hosts
```

### Solution 2: 코드 생성 프롬프트 강화 ✅

**파일**: `src/mact_langgraph/utils/prompt_utils.py:361-362`

```python
Requirements:
- ⚠️ CRITICAL: Use EXACT column names from the 'Available columns' comment in table setup
- All column names are lowercase (e.g., 'department_id', not 'Department_ID')
- Use pandas operations
- ...
```

**QWEN 프롬프트도 수정** (line 347):
```python
⚠️ CRITICAL: Use EXACT column names from the 'Available columns' comment above.
Write clean pandas code. End with: new_table = result
```

---

## 🎯 예상 효과

### Before (Bug):
```python
# Q12: "MTV Cube" theme 찾기
# LLM 생성 코드
result = df[df['Theme'] == 'MTV Cube']  # KeyError: 'Theme'
# → 3번 재시도 모두 실패
# → "Unable to perform operation"
```

### After (Fixed):
```python
# Q12: "MTV Cube" theme 찾기
# LLM이 프롬프트에서 정확한 컬럼명 확인:
# "Available columns: competition_id, year, theme, host_city_id, hosts"

# LLM 생성 코드
result = df[df['theme'] == 'MTV Cube']  # ✅ 성공!
# → competition_id=5, host_city_id=5
# → 다음 단계: city 테이블에서 Official_Name 조회
```

---

## 📊 기대 성과

### 직접적 개선
| 항목 | 현재 | 예상 | 변화 |
|------|------|------|------|
| **Q12 성공률** | 0% | 80-100% | +80-100%p |
| **Q15 성공률** | 0% | 60-80% | +60-80%p |
| **Q16 성공률** | 0% | 60-80% | +60-80%p |
| **"Unable" 발생률** | ~14% (3/21) | **~5%** | **-9%p** |

### 전체 정확도 영향
```
현재 정확도: 14.3% (3/21)
추가 개선 예상: +10-15%p (컬럼 KeyError 해결)
총 예상 정확도: 24-29%
```

### 간접적 효과
1. **재시도 감소**: KeyError로 인한 3번 재시도 제거 → 속도 개선
2. **에러율 감소**: "Unable to perform operation" 메시지 감소
3. **신뢰성 향상**: 일관된 컬럼명 사용으로 코드 실행 안정성 증가

---

## 🔬 검증 방법

### 테스트 1: Q12 단독 테스트
```bash
# Q12만 테스트 (farm competition + MTV Cube)
# Expected: host_city_id=5 → Aroostook
# Before: "Unable to determine answer"
# After: "Aroostook" (정답)
```

### 테스트 2: Q15, Q16 테스트
```bash
# Q15: cell_mobile_number lookup
# Q16: email lookup
# 둘 다 candidate_id 컬럼 사용
# Before: 'candidate_id' KeyError
# After: 정상 조회 예상
```

### 테스트 3: 전체 재실행
```bash
python main.py \
  --dataset_path ../datasets_examples/mmqa_samples.json \
  --plan_model gpt-3.5-turbo \
  --code_model gpt-3.5-turbo \
  --plan_sample 3 --code_sample 3 \
  --output_dir comparison_column_fix \
  --legacy_output
```

**성공 기준**:
- ✅ Q12, Q15, Q16에서 KeyError 제거
- ✅ "Unable to determine" 비율 14% → 5% 이하
- ✅ 전체 정확도 14.3% → 24%+ 달성

---

## 🚨 잠재적 리스크

### Risk 1: 여전히 다른 이유로 실패 가능
- **확률**: Medium
- **영향**: Q12, Q15, Q16이 여전히 오답일 수 있음
- **완화책**: 컬럼명 문제는 해결되지만 로직 오류는 별도 수정 필요

### Risk 2: LLM이 주석을 무시할 가능성
- **확률**: Low
- **영향**: 여전히 원본 컬럼명 사용
- **완화책**: "⚠️ CRITICAL" 강조로 주의 환기, 프롬프트에 명시적 지시

### Risk 3: 다른 질문에 부정적 영향
- **확률**: Very Low
- **영향**: 추가 정보로 인한 혼란
- **완화책**: 컬럼 리스트는 도움이 되지 해가 되지 않음

---

## 🔄 롤백 플랜

수정 사항이 문제를 일으킬 경우:

```bash
# table_utils.py에서 컬럼 주석 제거
git checkout HEAD -- src/mact_langgraph/utils/table_utils.py

# prompt_utils.py에서 프롬프트 변경 취소
git checkout HEAD -- src/mact_langgraph/utils/prompt_utils.py
```

---

## 📝 다음 단계

### Immediate (Today)
1. ✅ table2df()에 컬럼 리스트 추가
2. ✅ 코드 생성 프롬프트 강화
3. ⏭️ Q12 단독 테스트로 검증
4. ⏭️ 전체 데이터셋 재실행

### Short-term (This Week)
5. ⏭️ 결과 분석 및 추가 수정
6. ⏭️ 다른 실패 케이스 (Q5, Q8, Q20 regression) 분석
7. ⏭️ 답변 형식 검증 로직 추가

### Medium-term (Next Week)
8. ⏭️ 컬럼명 매핑 개선 (동적 매핑)
9. ⏭️ 에러 복구 메커니즘 강화
10. ⏭️ 프롬프트 최적화 지속

---

## 📚 참고 자료

### 수정된 파일
1. `src/mact_langgraph/utils/table_utils.py` (line 146-149)
2. `src/mact_langgraph/utils/prompt_utils.py` (line 347, 361-362)

### 관련 문서
- `logs_ai/BUG_FIX_PLAN.md` - 원래 Bug #1 분석
- `logs_ai/COMPARISON_FIXED_VS_BASELINE.md` - 비교 테스트 결과
- `logs_ai/CHECKPOINT_2025_09_30.md` - 이전 체크포인트

### 테스트 결과
- `comparison_fixed_v1/` - 수정 전 결과 (14.3% accuracy)
- `test_column_fix/` - 수정 후 초기 테스트

---

**작성 완료**: 2025-10-02 05:05
**상태**: ✅ 코드 수정 완료, 테스트 대기 중
**예상 다음 단계**: 전체 데이터셋 재실행 및 결과 분석
