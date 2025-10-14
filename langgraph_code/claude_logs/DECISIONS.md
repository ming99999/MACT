# Design Decisions Log

This document records key design decisions made during the Multi-Agent framework development.

---

## Decision 1: Multi-Agent Architecture Pattern

**Date**: 2025-10-13
**Context**: Need to extend MACT with EDA capabilities and flexible output formatting
**Decision**: Use specialized agent pattern with LangGraph orchestration

**Options Considered**:
1. Monolithic extension of existing MACT
2. Pipeline pattern (sequential agents without orchestration)
3. Multi-agent with LangGraph orchestration (chosen)

**Rationale**:
- ✅ **Modularity**: Each agent has clear responsibility
- ✅ **Extensibility**: Easy to add R-Zero agents in Step 2
- ✅ **Reusability**: Leverage existing LangGraph infrastructure
- ✅ **Flexibility**: Can modify individual agents without affecting others
- ✅ **State Management**: LangGraph handles state passing cleanly

**Trade-offs**:
- ➖ Additional orchestration overhead (~10-20% execution time)
- ➖ More complex initial setup
- ➕ Better long-term maintainability
- ➕ Easier debugging (isolated agent behavior)

---

## Decision 2: EDA Agent Placement

**Date**: 2025-10-13
**Context**: Where should EDA Agent execute in the workflow?
**Decision**: Run EDA Agent once at the beginning, before planning loop

**Options Considered**:
1. Run EDA inside planning loop (every iteration)
2. Run EDA once at the beginning (chosen)
3. Run EDA on-demand when needed

**Rationale**:
- ✅ **Efficiency**: Avoid redundant table analysis
- ✅ **Context Stability**: Consistent context throughout reasoning
- ✅ **Performance**: Minimal overhead (~1-2s one-time cost)
- ⚠️ **Assumption**: Table properties don't change during reasoning

**Implementation**:
```
Input → EDA Agent (analyze tables) → Planning Loop (uses EDA context)
```

---

## Decision 3: Report Agent Functionality

**Date**: 2025-10-13
**Context**: Need flexible output formatting for different use cases
**Decision**: Report Agent as post-processor with configurable output formats

**Requirements**:
1. **For MMQA Dataset**: JSON output with subtasks (FK, PK, SQL, answer)
2. **For Business Use**: Natural language report with reasoning chain
3. **For Research**: Detailed execution log with token usage

**Design**:
- Report Agent receives final state + output format specification
- Uses template-based generation with LLM assistance
- Configurable via `output_format` parameter in state

**Output Format Types**:
```python
output_format: "mmqa_json" | "business_report" | "research_detailed" | "simple_answer"
```

---

## Decision 4: State Schema Extension Strategy

**Date**: 2025-10-13
**Context**: Need to extend MACTState without breaking existing code
**Decision**: Create new `MultiAgentState` that inherits from `MACTState`

**Rationale**:
- ✅ **Backward Compatibility**: Existing MACT code still works
- ✅ **Clean Separation**: Multi-agent specific fields are clearly marked
- ✅ **Type Safety**: TypedDict ensures correct field usage
- ✅ **Documentation**: New fields are well-documented

**New Fields Added**:
```python
class MultiAgentState(MACTState):
    # EDA Agent outputs
    eda_context: str
    table_statistics: Dict[str, Any]
    detected_foreign_keys: List[str]
    column_types: Dict[str, Dict[str, str]]
    value_patterns: Dict[str, Any]

    # Report Generator outputs
    output_format: str
    reasoning_report: str
    confidence_breakdown: Dict[str, float]
    formatted_output: Dict[str, Any]
```

---

## Decision 5: Reuse vs. Rewrite of MACT Components

**Date**: 2025-10-13
**Context**: Existing MACT nodes (planner, tool_nodes, observer) are functional
**Decision**: Wrap existing nodes as agents rather than full rewrite

**Strategy**:
- **Planning Agent**: Thin wrapper around `planner_node` with EDA context injection
- **Coding Agent**: Wrapper around `tool_nodes` with minimal modifications
- **Validator Agent**: Extension of `observer_node` with enhanced validation
- **EDA Agent**: Completely new implementation
- **Report Agent**: Completely new implementation

**Rationale**:
- ✅ **Efficiency**: Leverage proven code (42.9% accuracy baseline)
- ✅ **Risk Mitigation**: Avoid introducing new bugs
- ✅ **Speed**: Faster development (~50% time savings)
- ⚠️ **Technical Debt**: May need refactoring later for full agent paradigm

---

## Decision 6: EDA Agent Core Capabilities

**Date**: 2025-10-13
**Context**: What analysis should EDA Agent perform?
**Decision**: Focus on actionable insights for table QA

**Capabilities** (Priority Order):
1. **Table Schema Analysis**
   - Column names and data types
   - Null value ratios
   - Unique value counts

2. **Foreign Key Detection** (Critical for MMQA)
   - Column name similarity matching
   - Value overlap analysis
   - PK-FK relationship inference

3. **Statistical Profiling**
   - Numeric column ranges and distributions
   - Categorical value frequencies
   - Date/time patterns

4. **Natural Language Context Generation**
   - Human-readable table descriptions
   - Relationship summaries
   - Domain knowledge hints

**Out of Scope** (for now):
- Complex statistical tests (correlation, etc.)
- Data quality anomaly detection
- Schema normalization suggestions

**Rationale**:
- ✅ **Focus**: Capabilities directly support table QA task
- ✅ **Performance**: Keep analysis under 2 seconds per question
- ✅ **Simplicity**: Avoid over-engineering

---

## Decision 7: Documentation Strategy

**Date**: 2025-10-13
**Context**: Need to maintain context across long development sessions
**Decision**: Use `claude_logs/` directory with three core documents

**Documents**:
1. **PROJECT_CONTEXT.md**: Big picture, goals, architecture
2. **CURRENT_TASK.md**: Current phase details, progress tracking
3. **DECISIONS.md**: Design rationale and trade-offs (this file)

**Update Frequency**:
- **PROJECT_CONTEXT.md**: Update at major milestones (phase completion)
- **CURRENT_TASK.md**: Update at end of each work session
- **DECISIONS.md**: Update when making significant design choices

**Rationale**:
- ✅ **Context Preservation**: Easy to resume work after breaks
- ✅ **Decision Tracking**: Understand why choices were made
- ✅ **Collaboration**: Clear for other developers/AI assistants

---

## Future Decisions to Make

### Pending for Phase 2 (EDA Agent Implementation)
- [ ] EDA prompt engineering: Few-shot vs. zero-shot?
- [ ] FK detection algorithm: Heuristic vs. LLM-based vs. hybrid?
- [ ] Context compression: How to keep EDA context concise?

### Pending for Phase 3 (Agent Refactoring)
- [ ] Agent communication: Direct state passing vs. message queue?
- [ ] Error handling: Retry logic at agent level or orchestrator level?

### Pending for Phase 4 (Report Generator)
- [ ] Template engine: Jinja2 vs. f-strings vs. LLM-based generation?
- [ ] Output validation: Schema enforcement for JSON outputs?

---

## Decision Review Process

Before each phase:
1. Review relevant pending decisions
2. Make decisions based on current context
3. Document rationale
4. Update implementation plan if needed
