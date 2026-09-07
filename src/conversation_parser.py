"""
Sprint 4 — LangGraph conversation parser

A small state graph: extract -> validate -> (retry once on failure) -> done.
Keeping it as an explicit graph (rather than one long prompt) makes the
retry-on-invalid-JSON behavior a first-class, testable node instead of a
try/except wrapped around a single LLM call.
"""
import asyncio
import json
import time
from typing import TypedDict, Optional

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from pydantic import ValidationError

from src.config import settings
from src.schemas import ConversationEvent

EXTRACTION_PROMPT = """You convert a spoken transcript into JSON with exactly these fields:
transcript (string), intent (one of: navigate, query, chat, command),
entities (object of short key-value strings extracted from the transcript).
Return ONLY valid JSON, no prose, no markdown fences.

Transcript: "{transcript}"
"""


class ParserState(TypedDict):
    transcript: str
    lat: Optional[float]
    lon: Optional[float]
    raw_output: Optional[str]
    event: Optional[ConversationEvent]
    error: Optional[str]
    attempts: int


def _get_llm():
    return ChatOpenAI(model="gpt-4o-mini", api_key=settings.openai_api_key, temperature=0)


def extract_node(state: ParserState) -> ParserState:
    llm = _get_llm()
    prompt = EXTRACTION_PROMPT.format(transcript=state["transcript"])
    response = llm.invoke(prompt)
    state["raw_output"] = response.content
    state["attempts"] += 1
    return state


def validate_node(state: ParserState) -> ParserState:
    try:
        parsed = json.loads(state["raw_output"])
        event = ConversationEvent(
            transcript=state["transcript"],
            intent=parsed.get("intent", "chat"),
            entities=parsed.get("entities", {}),
            lat=state.get("lat"),
            lon=state.get("lon"),
            timestamp=time.time(),
            source="llm",
        )
        state["event"] = event
        state["error"] = None
    except (json.JSONDecodeError, ValidationError) as exc:
        state["error"] = str(exc)
    return state


def route_after_validate(state: ParserState) -> str:
    if state["event"] is not None:
        return END
    if state["attempts"] < 2:
        return "extract"
    return END  # give up after one retry; orchestrator falls back on-device


def build_parser_graph():
    graph = StateGraph(ParserState)
    graph.add_node("extract", extract_node)
    graph.add_node("validate", validate_node)
    graph.set_entry_point("extract")
    graph.add_edge("extract", "validate")
    graph.add_conditional_edges("validate", route_after_validate, {"extract": "extract", END: END})
    return graph.compile()


async def parse_transcript(transcript: str, lat: float = None, lon: float = None) -> ConversationEvent | None:
    graph = build_parser_graph()
    initial_state: ParserState = {
        "transcript": transcript, "lat": lat, "lon": lon, "raw_output": None,
        "event": None, "error": None, "attempts": 0,
    }
    # graph.invoke() and the underlying llm.invoke() are BLOCKING calls. Running
    # them directly in this coroutine would freeze the whole event loop and make
    # asyncio.wait_for's timeout in the orchestrator unable to fire on schedule.
    # Offloading to a thread lets the orchestrator's timeout actually preempt
    # a slow/hanging OpenAI call instead of waiting for it to finish.
    loop = asyncio.get_event_loop()
    result: ParserState = await loop.run_in_executor(None, graph.invoke, initial_state)
    return result["event"]
