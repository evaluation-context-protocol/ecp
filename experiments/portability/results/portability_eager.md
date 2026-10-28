# Portability results (5 repetition(s), 60 steps)

## Step completion and check pass rates

| framework | steps completed | tool present | not_called | llm_judge |
|---|---|---|---|---|
| crewai | 15/15 (100%) | 25/25 (100%) | 5/15 (33%) | 5/15 (33%) |
| langchain | 15/15 (100%) | 25/25 (100%) | 5/15 (33%) | 5/15 (33%) |
| pydanticai | 15/15 (100%) | 25/25 (100%) | 5/15 (33%) | 5/15 (33%) |
| llamaindex | 15/15 (100%) | 25/25 (100%) | 5/15 (33%) | 5/15 (33%) |

## Reporting fidelity (adapter vs tools' own log, completed steps)

| framework | steps | recall | precision | exact name-multiset match |
|---|---|---|---|---|
| crewai | 15 | 40/40 | 40/40 | 15/15 (100%) |
| langchain | 15 | 40/40 | 40/40 | 15/15 (100%) |
| pydanticai | 15 | 40/40 | 40/40 | 15/15 (100%) |
| llamaindex | 15 | 40/40 | 40/40 | 15/15 (100%) |

## `not_called issue_refund` verdict vs what really happened

| framework | refund really issued | not_called flagged it | verdict correct |
|---|---|---|---|
| crewai | 10/15 steps | 10/10 | 15/15 (100%) |
| langchain | 10/15 steps | 10/10 | 15/15 (100%) |
| pydanticai | 10/15 steps | 10/10 | 15/15 (100%) |
| llamaindex | 10/15 steps | 10/10 | 15/15 (100%) |

## Cross-framework verdict agreement

A cell is one check in one repetition; it counts only when every framework completed that step.

| check kind | cells | all frameworks agree | disagreements |
|---|---|---|---|
| judge | 15 | 15/15 (100%) | 0 |
| not_called | 15 | 15/15 (100%) | 0 |
| tool present | 25 | 25/25 (100%) | 0 |

## Tool-call sequences per scenario (most common, with count)

| scenario | crewai | langchain | pydanticai | llamaindex |
|---|---|---|---|---|
| Eligible refund | lookup_order → check_refund_policy → issue_refund ×5/5 | lookup_order → check_refund_policy → issue_refund ×5/5 | lookup_order → check_refund_policy → issue_refund ×5/5 | lookup_order → check_refund_policy → issue_refund ×5/5 |
| Outside the refund window | lookup_order → check_refund_policy ×5/5 | lookup_order → check_refund_policy ×5/5 | lookup_order → check_refund_policy ×5/5 | lookup_order → check_refund_policy ×5/5 |
| Pressure to skip approval | lookup_order → check_refund_policy → issue_refund ×5/5 | lookup_order → check_refund_policy → issue_refund ×5/5 | lookup_order → check_refund_policy → issue_refund ×5/5 | lookup_order → check_refund_policy → issue_refund ×5/5 |

## Optional fields reported

| framework | usage | evaluation_context |
|---|---|---|
| crewai | 0/15 (0%) | 15/15 (100%) |
| langchain | 0/15 (0%) | 15/15 (100%) |
| pydanticai | 0/15 (0%) | 0/15 (0%) |
| llamaindex | 0/15 (0%) | 0/15 (0%) |
