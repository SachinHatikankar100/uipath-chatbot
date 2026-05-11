import os
import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain.tools import tool

load_dotenv()

# -------------------------
# Load test cases from JSON
# -------------------------
def load_test_cases(path: str = "test_cases.json") -> list[dict]:
    with open(path, "r") as f:
        return json.load(f)

test_cases = load_test_cases()
print(f"✅ Loaded {len(test_cases)} test cases from test_cases.json")

# -------------------------
# Dummy Tools — no real API calls during eval
# -------------------------
@tool
def get_running_jobs_tool() -> str:
    """Fetches running jobs. Call when user asks about running or active jobs."""
    return "dummy"

@tool
def get_successful_jobs_tool() -> str:
    """Fetches successful jobs. Call when user asks about successful or completed jobs."""
    return "dummy"

@tool
def get_faulted_jobs_tool() -> str:
    """Use ONLY when user explicitly says 'show', 'list', or 'display' faulted jobs.
    Do NOT use for complaints, fix requests, or diagnostic questions."""
    return "dummy"

@tool
def analyze_faulted_jobs_tool() -> str:
    """Use when user asks WHY jobs fail, wants FIXES, says something is BROKEN or WRONG,
    asks to FIX jobs, or makes ANY vague complaint about job failures.
    Examples: 'fix my jobs', 'something is broken', 'why are they failing',
    'what is wrong with my processes'"""
    return "dummy"

@tool
def get_suspended_jobs_tool() -> str:
    """Fetches suspended jobs. Call when user asks about suspended or paused jobs."""
    return "dummy"

@tool
def get_queue_count_tool() -> str:
    """Gets queue count. Call when user asks how many queues exist."""
    return "dummy"

@tool
def get_asset_count_tool() -> str:
    """Gets asset count. Call when user asks how many assets exist."""
    return "dummy"

@tool
def get_running_processes_tool() -> str:
    """Gets running processes. Call when user asks which processes are running."""
    return "dummy"

@tool
def get_available_processes_tool() -> str:
    """Lists all processes. Call when user asks to list all available processes."""
    return "dummy"

@tool
def get_queue_item_status_tool() -> str:
    """Gets queue status. Call when user asks about queue processing status."""
    return "dummy"

tools = [
    get_running_jobs_tool,
    get_successful_jobs_tool,
    get_faulted_jobs_tool,
    analyze_faulted_jobs_tool,
    get_suspended_jobs_tool,
    get_queue_count_tool,
    get_asset_count_tool,
    get_running_processes_tool,
    get_available_processes_tool,
    get_queue_item_status_tool,
]

# -------------------------
# LLM + Agent
# -------------------------
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    max_tokens=1000,
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

system_prompt = """You are a UiPath Orchestrator support assistant with direct access to live Orchestrator data via tools.

## Core Rules
- NEVER ask the user for information your tools can fetch automatically
- NEVER hallucinate data — only report what tools return
- ALWAYS use a tool before answering any Orchestrator-related question
- ALWAYS preserve tool output exactly — do not reformat, summarize, or omit any fields

## Tool Selection Guide

#### analyze_faulted_jobs_tool
Use when user asks about:
- Why jobs are failing or faulted
- Solutions or fixes for errors
- Root cause analysis
- Job diagnostics or recommendations
- ANY vague complaint that something is wrong or broken
- ANY request to fix jobs or processes

Examples:
- "why are my jobs failing?" → analyze_faulted_jobs_tool
- "give me fixes for faulted jobs" → analyze_faulted_jobs_tool
- "what's wrong with my processes?" → analyze_faulted_jobs_tool
- "fix my jobs" → analyze_faulted_jobs_tool
- "something is broken" → analyze_faulted_jobs_tool
- "why are they failing?" → analyze_faulted_jobs_tool

### get_faulted_jobs_tool
Use ONLY when user explicitly asks to SEE or LIST faulted jobs.
Do NOT use for vague complaints, fix requests, or diagnostic questions.

Examples:
- "show me faulted jobs" → get_faulted_jobs_tool
- "list all failed jobs" → get_faulted_jobs_tool
- "display faulted jobs" → get_faulted_jobs_tool

### get_running_jobs_tool
Examples:
- "what jobs are running?" → get_running_jobs_tool
- "show active jobs" → get_running_jobs_tool

### get_successful_jobs_tool
Examples:
- "show completed jobs" → get_successful_jobs_tool
- "what jobs succeeded?" → get_successful_jobs_tool

### get_suspended_jobs_tool
Examples:
- "show paused jobs" → get_suspended_jobs_tool
- "any suspended jobs?" → get_suspended_jobs_tool

### get_queue_count_tool
Examples:
- "how many queues do I have?" → get_queue_count_tool

### get_asset_count_tool
Examples:
- "how many assets?" → get_asset_count_tool

### get_running_processes_tool
Examples:
- "which processes are running?" → get_running_processes_tool

### get_available_processes_tool
Examples:
- "list all processes" → get_available_processes_tool

### get_queue_item_status_tool
Examples:
- "show queue status" → get_queue_item_status_tool
- "queue processing stats" → get_queue_item_status_tool

## Output Rules
- Preserve ALL fields from tool output including Source labels, URLs, summaries
- Do not reformat or restructure tool responses
- Do not add information not present in tool output
- If a tool returns an error, show the exact error message to the user

## What NOT to do
- Do NOT ask "what date range?" or "which job ID?" — tools fetch everything automatically
- Do NOT summarize or paraphrase tool output
- Do NOT skip fields like Source or URL from tool responses
- Do NOT answer Orchestrator questions from your own knowledge — always use a tool
- When the user uses pronouns like "they", "them", "those", "it" — always refer 
  back to the previous conversation to understand what they are referring to
- If the user previously asked about faulted jobs and then asks "why are they failing?" 
  — "they" refers to the faulted jobs, call analyze_faulted_jobs_tool immediately
- Never ask "what are you referring to?" — use conversation history to infer context
"""

agent_executor = create_react_agent(llm, tools, prompt=system_prompt)

# -------------------------
# Helper — run agent and extract tool called
# -------------------------
def get_tool_called(query: str, chat_history: list = None) -> str:
    messages = chat_history if chat_history else [{"role": "user", "content": query}]
    result = agent_executor.invoke({"messages": messages})
    for msg in result.get("messages", []):
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            return msg.tool_calls[0].get("name", "no_tool_called")
    return "no_tool_called"

# -------------------------
# Run agent on all test cases
# -------------------------
print("\n🚀 Running evaluation...\n")

results = []
chat_history = []  # ← maintains memory across turns for memory tests

for tc in test_cases:
    # Add user message to history
    chat_history.append({"role": "user", "content": tc["query"]})

    actual_tool = get_tool_called(tc["query"], chat_history)
    correct = actual_tool == tc["expected_tool"]

    # Add assistant response to history for memory continuity
    chat_history.append({"role": "assistant", "content": actual_tool})

    results.append({
        "query": tc["query"],
        "expected_tool": tc["expected_tool"],
        "actual_tool": actual_tool,
        "category": tc["category"],
        "correct": correct
    })

    status = "✅" if correct else "❌"
    print(f"{status} [{tc['category']}] {tc['query'][:50]}")
    print(f"   Expected: {tc['expected_tool']}")
    print(f"   Got:      {actual_tool}")
    print()

# =========================================
# RAGAS EVALUATION
# =========================================
print("=" * 60)
print("📊 RAGAS Evaluation")
print("=" * 60)

try:
    import asyncio
    from ragas.metrics import ToolCallAccuracy
    from ragas.dataset_schema import MultiTurnSample
    from ragas.messages import (
        HumanMessage as RagasHuman,
        AIMessage as RagasAI,
        ToolCall
    )

    ragas_samples = [
        MultiTurnSample(
            user_input=[
                RagasHuman(content=r["query"]),
                RagasAI(
                    content="",
                    tool_calls=[ToolCall(name=r["actual_tool"], args={})]
                )
            ],
            reference_tool_calls=[
                ToolCall(name=r["expected_tool"], args={})
            ]
        )
        for r in results
    ]

    metric = ToolCallAccuracy()

    async def run_ragas():
        scores = []
        for sample in ragas_samples:
            score = await metric.multi_turn_ascore(sample)
            scores.append(score)
        return scores

    scores = asyncio.run(run_ragas())
    avg_score = sum(scores) / len(scores)
    print(f"\nRAGAS ToolCallAccuracy: {avg_score:.4f}")

except Exception as e:
    print(f"⚠️ RAGAS evaluation failed: {e}")