"""
Request validation schemas (pydantic)
"""

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

from config import Config


class HistoryTurn(BaseModel):
    question: str
    answer: str


class QueryRequest(BaseModel):
    question: str = Field(min_length=1)
    n_results: int = Field(default=5, ge=1, le=20)
    use_hybrid: bool = True
    use_context: bool = True
    history: Optional[List[HistoryTurn]] = None

    @field_validator('question')
    @classmethod
    def strip_question(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('Question cannot be empty')
        return v

    @field_validator('history')
    @classmethod
    def cap_history(cls, v: Optional[List[HistoryTurn]]) -> Optional[List[HistoryTurn]]:
        if v is None:
            return v
        return v[-Config.MAX_HISTORY_TURNS:]


class DeleteDocumentRequest(BaseModel):
    source: str = Field(min_length=1)
