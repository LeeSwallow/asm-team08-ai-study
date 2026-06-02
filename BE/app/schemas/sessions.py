from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    caseId: str = Field(default="case_001")


class AskQuestionRequest(BaseModel):
    questionId: Optional[str] = None
    questionText: Optional[str] = None
    suspectId: Optional[str] = None


class DialogueRequest(BaseModel):
    suspectId: str
    message: str
    questionId: Optional[str] = None


class AccusationRequest(BaseModel):
    suspectId: str
    motive: Optional[str] = None
    method: Optional[str] = None
    evidenceIds: List[str] = Field(default_factory=list)
    contradictionIds: List[str] = Field(default_factory=list)
    statementIds: List[str] = Field(default_factory=list)


class NotesSummaryRequest(BaseModel):
    note: str = ""


class NoteRequest(BaseModel):
    text: str
    tags: List[str] = Field(default_factory=list)
    linkedStatementIds: List[str] = Field(default_factory=list)
    linkedEvidenceIds: List[str] = Field(default_factory=list)
    linkedRecordIds: List[str] = Field(default_factory=list)


class NoteUpdateRequest(BaseModel):
    text: Optional[str] = None
    tags: Optional[List[str]] = None
    linkedStatementIds: Optional[List[str]] = None
    linkedEvidenceIds: Optional[List[str]] = None
    linkedRecordIds: Optional[List[str]] = None


class BookmarkRequest(BaseModel):
    targetType: Literal["dialogue", "statement", "evidence", "record", "relation"]
    targetId: str
    note: Optional[str] = None


class DebugPressureRequest(BaseModel):
    suspectId: str
    pressure: int = Field(ge=0, le=100)


class DebugUnlockRequest(BaseModel):
    target: Literal["evidence", "relations", "timeline", "notes", "all"]
