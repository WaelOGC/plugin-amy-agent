"""Pydantic models for the Submit Your Idea conversation engine."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.messages import AiConfig

SubmitIdeaStatus = Literal[
    "collecting",
    "confirming",
    "deep_dive",
    "awaiting_contact",
    "completed",
]

QuestionType = Literal["text", "textarea", "single_choice", "multi_choice"]


class SubmitIdeaQuestion(BaseModel):
    id: str
    text: str
    type: QuestionType
    options: list[str] = Field(default_factory=list)
    required: bool = True


class SubmitIdeaTemplate(BaseModel):
    slug: str
    label: str
    questions: list[SubmitIdeaQuestion]


class SubmitIdeaStartRequest(BaseModel):
    session_id: str
    service_slug: str


class SubmitIdeaStartResponse(BaseModel):
    session_id: str
    status: SubmitIdeaStatus
    template: SubmitIdeaTemplate


class SubmitIdeaAnswersRequest(BaseModel):
    session_id: str
    answers: dict[str, Any]
    ai: AiConfig


class SubmitIdeaAnswersResponse(BaseModel):
    session_id: str
    status: SubmitIdeaStatus
    summary_text: str
    numbered_items: list[str]


class SubmitIdeaConfirmRequest(BaseModel):
    session_id: str
    confirmed: bool
    ai: AiConfig | None = None


class SubmitIdeaConfirmResponse(BaseModel):
    session_id: str
    status: SubmitIdeaStatus
    message: str


class SubmitIdeaDeepDiveRequest(BaseModel):
    session_id: str
    message: str
    ai: AiConfig


class SubmitIdeaDeepDiveResponse(BaseModel):
    session_id: str
    status: SubmitIdeaStatus
    reply: str


class SubmitIdeaContactRequest(BaseModel):
    session_id: str
    email: str
    whatsapp: str | None = None
    ai: AiConfig | None = None


class SubmitIdeaContactInfo(BaseModel):
    email: str
    whatsapp: str | None = None


class SubmitIdeaBrief(BaseModel):
    service_slug: str
    service_label: str
    answers: dict[str, Any]
    free_conversation_summary: str | None = None
    contact: SubmitIdeaContactInfo
    attachments: list[str] = Field(default_factory=list)


class SubmitIdeaContactResponse(BaseModel):
    session_id: str
    status: SubmitIdeaStatus
    brief: SubmitIdeaBrief


class SubmitIdeaUploadResponse(BaseModel):
    filename: str
    url: str
