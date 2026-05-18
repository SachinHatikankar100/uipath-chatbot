import os
import asyncio
import requests
import streamlit as st
from dotenv import load_dotenv
from tabulate import tabulate
from langchain.tools import tool
#from langchain_ollama import ChatOllama #not used and commented
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
#from langchain.agents import create_react_agent - new way to work but does not work hence commented 
#from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_tavily import TavilySearch
from pydantic import BaseModel
from nemoguardrails import RailsConfig, LLMRails
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from langchain_community.cache import InMemoryCache
from langchain_core.globals import set_llm_cache

# -------------------------
# LLM Caching
# -------------------------
set_llm_cache(InMemoryCache())
print("✅ LLM Cache active") #Keeping this because it will tell whether cache is working 

# -------------------------
# Structured Output Models
# -------------------------
class TavilySolution(BaseModel):
    title:str
    url:str
    summary:str


class FaultedJobReport(BaseModel):
    job_id:int
    process:str
    error:str
    solutions:list[TavilySolution]
    search_source:str = "Unknown"

class FaultedJobAnalysis(BaseModel):
    total_faulted:int
    reports:list[FaultedJobReport]







# -------------------------
# Load ENV
# -------------------------
load_dotenv()

UIPATH_ACCESS_TOKEN = os.getenv("UIPATH_ACCESS_TOKEN")
UIPATH_ORG = os.getenv("UIPATH_ORG")
UIPATH_TENANT = os.getenv("UIPATH_TENANT")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

st.set_page_config(page_title="UiPath Orchestrator Support Chatbot", page_icon="🤖", layout="wide")

if not UIPATH_ACCESS_TOKEN:
    st.error("Missing UIPATH_ACCESS_TOKEN in .env")
    st.stop()

if not UIPATH_ORG or not UIPATH_TENANT:
    st.error("Missing UIPATH_ORG or UIPATH_TENANT in .env")
    st.stop()

if not TAVILY_API_KEY:
    st.error("Missing TAVILY_API_KEY in .env")
    st.stop()

os.environ["TAVILY_API_KEY"] = TAVILY_API_KEY

BASE_URL = f"https://cloud.uipath.com/{UIPATH_ORG}/{UIPATH_TENANT}/orchestrator_"

HEADERS = {
    "Authorization": f"Bearer {UIPATH_ACCESS_TOKEN}",
    "X-UIPATH-TenantName": UIPATH_TENANT,
    "Content-Type": "application/json",
    "X-UIPATH-OrganizationUnitId": os.getenv("UIPATH_FOLDER_ID")
}

# -------------------------
# Retry configuration
# -------------------------
orchestrator_retry = retry(
stop = stop_after_attempt(3),
wait = wait_exponential(multiplier=1, min=2, max=10),
retry = retry_if_exception_type(requests.exceptions.RequestException),
reraise=True
)


# -------------------------
# API Helpers
# -------------------------
@orchestrator_retry
def call_orchestrator(url: str):
    response = requests.get(url, headers=HEADERS)
    #response = requests.get("http://localhost:9999", headers=HEADERS) - this for testing url retry
    if response.status_code == 401:
        return None, "Unauthorized - check your UiPath access token."
    if response.status_code == 429:
        raise requests.exceptions.RequestException("Rate limited - retrying...")
    if response.status_code >= 500:
        raise requests.exceptions.RequestException(f"Server error {response.status_code} - retrying...")
    if response.status_code != 200:
        return None, f"API failed | {response.status_code} | {response.text}"
    return response.json(), None

@orchestrator_retry
def call_orchestrator_count(url: str):
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 401:
        return None, "Unauthorized - check your UiPath access token."
    if response.status_code == 429:
        raise requests.exceptions.RequestException("Rate limited - retrying...")
    if response.status_code >= 500:
        raise requests.exceptions.RequestException(f"Server error {response.status_code} - retrying...")
    if response.status_code != 200:
        return None, f"API failed | {response.status_code} | {response.text}"
    data = response.json()
    count = data.get("@odata.count")
    return count, None






# -------------------------
# JOBS
# -------------------------
def format_jobs_table(jobs, state):
    if not jobs:
        return f"✅ No jobs found in state: {state}"

    pretty_jobs = []
    for job in jobs:
        pretty_jobs.append({
            "Id": job.get("Id"),
            "State": job.get("State"),
            "StartTime": job.get("StartTime"),
            "EndTime": job.get("EndTime"),
            "Robot": job.get("Robot", {}).get("Name") if job.get("Robot") else None,
            "Release": job.get("ReleaseName"),
            "Source": job.get("Source"),
            "Info": job.get("Info")
        })

    table = tabulate(pretty_jobs, headers="keys", tablefmt="html")
    return f"📌 Jobs in state: {state}\n\n{table}"


def get_jobs_by_state(state: str):
    url = f"{BASE_URL}/odata/Jobs?$filter=State eq '{state}'"
    data, err = call_orchestrator(url)
    if err:
        return None, err
    return data.get("value", []), None


def get_running_jobs():
    return get_jobs_by_state("Running")

def get_successful_jobs():
    return get_jobs_by_state("Successful")

def get_faulted_jobs():
    return get_jobs_by_state("Faulted")

def get_suspended_jobs():
    return get_jobs_by_state("Suspended")


# -------------------------
# COUNTS
# -------------------------
def get_queue_count():
    url = f"{BASE_URL}/odata/QueueDefinitions"
    return call_orchestrator_count(url)

def get_asset_count():
    url = f"{BASE_URL}/odata/Assets/UiPath.Server.Configuration.OData.GetAssetsAcrossFolders"
    return call_orchestrator_count(url)


# -------------------------
# QUEUE ITEMS STATUS
# -------------------------
def get_queue_item_status():
    url = f"{BASE_URL}/odata/QueueProcessingRecords/UiPathODataSvc.RetrieveQueuesProcessingStatus"
    data, err = call_orchestrator(url)
    if err:
        return None, err

    names_url = f"{BASE_URL}/odata/QueueDefinitions?$select=Id,Name"
    names_data, err = call_orchestrator(names_url)
    if err:
        return None, err

    name_map = {q["Id"]: q["Name"] for q in names_data.get("value", [])}
    records = data.get("value", [])
    for r in records:
        r["QueueName"] = name_map.get(r.get("QueueDefinitionId"), "Unknown")

    return records, None


# -------------------------
# RUNNING / AVAILABLE PROCESSES
# -------------------------
def get_running_processes():
    jobs, err = get_running_jobs()
    if err:
        return None, err

    process_map = {}
    for job in jobs:
        process_name = job.get("ReleaseName", "UnknownProcess")
        process_map[process_name] = process_map.get(process_name, 0) + 1

    return process_map, None


def get_available_processes():
    url = f"{BASE_URL}/odata/Releases?$select=Name,ProcessKey,EnvironmentId"
    data, err = call_orchestrator(url)
    if err:
        return None, err
    return data.get("value", []), None


# -------------------------
# Formatting Helpers
# -------------------------
def format_running_processes(process_map):
    if not process_map:
        return "✅ No processes are currently running."
    rows = [{"Process Name": name, "Running Jobs": count}
            for name, count in sorted(process_map.items(), key=lambda x: x[1], reverse=True)]
    return f"🟢 Running Processes\n\n{tabulate(rows, headers='keys', tablefmt='fancy_grid')}"


def format_available_processes(processes):
    if not processes:
        return "⚠️ No processes found in Orchestrator."
    rows = [{"Name": p.get("Name"), "ProcessKey": p.get("ProcessKey"), "EnvironmentId": p.get("EnvironmentId")}
            for p in processes]
    return f"📦 Available Processes ({len(processes)})\n\n{tabulate(rows, headers='keys', tablefmt='fancy_grid')}"


def format_queue_item_status(records):
    if not records:
        return "⚠️ No queue processing records found."
    rows = [{
        "Queue Name": r.get("QueueName"),
        "Queue ID": r.get("QueueDefinitionId"),
        "Successful": r.get("NumberOfSuccessfulTransactions"),
        "App Exceptions": r.get("NumberOfApplicationExceptions"),
        "Biz Exceptions": r.get("NumberOfBusinessExceptions"),
        "Total": r.get("TotalNumberOfTransactions"),
        "Report Type": r.get("ReportType"),
    } for r in records]
    return f"📊 Queue Processing Status ({len(records)} records)\n\n{tabulate(rows, headers='keys', tablefmt='fancy_grid')}"


# -------------------------
# Extract Error Summaries from Faulted Jobs
# -------------------------
def extract_faulted_error_summaries(jobs: list) -> list[dict]:
    """
    Pulls out meaningful error details from faulted jobs
    to build targeted Tavily search queries.
    """
    summaries = []
    query_llm = ChatOpenAI(model="gpt-4o-mini",
            temperature=0,
            max_tokens=4000,
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY")
                        )
    for job in jobs:
        info = job.get("Info", "") or ""
        release = job.get("ReleaseName", "UnknownProcess")

        # Trim long stack traces — keep only the first meaningful line
        first_line = info.strip().split("\n")[0][:300] if info else "Unknown error"
        


        prompt = f"""
        You are a search query generator for UiPath RPA errors.
        Convert this exact technical error into a precise search query.

        Error: {first_line}
        Process: {release}

        Rules:
        - Maximum 10 words
        - Expand any mathematical notation to words (e.g. 1/0 = divide by zero)
        - Include the exception type if present (e.g. SystemException, NullReferenceException)
        - Focus on the technical root cause, not the process name
        - Return ONLY the search query, nothing else

        Example:
        Error: System.DivideByZeroException: 1/0 is not valid
        Output: UiPath SystemException divide by zero workflow fix
        """


        readable_query = query_llm.invoke(prompt).content.strip()
        print(f"DEBUG - Generated query: {readable_query}")
        summaries.append({
            "job_id": job.get("Id"),
            "release": release,
            "error": first_line,
            "readable_query": readable_query 
        })
    return summaries


# -------------------------
# Tools
# -------------------------
@tool
def get_running_jobs_tool() -> str:
    """Fetches all currently running jobs from UiPath Orchestrator.
    Call this when user asks about running jobs, active jobs, or jobs in progress."""
    jobs, err = get_running_jobs()
    return err if err else format_jobs_table(jobs, "Running")

@tool
def get_successful_jobs_tool() -> str:
    """Fetches all successful/completed jobs from UiPath Orchestrator.
    Call this when user asks about successful jobs or completed jobs."""
    jobs, err = get_successful_jobs()
    return err if err else format_jobs_table(jobs, "Successful")

@tool
def get_faulted_jobs_tool() -> str:
    """Fetches all faulted/failed jobs from UiPath Orchestrator and returns job details.
    Call this when user asks about failed jobs, faulted jobs, or job errors.
    After fetching, you MUST call analyze_faulted_jobs_tool to search for solutions."""
    jobs, err = get_faulted_jobs()
    return err if err else format_jobs_table(jobs, "Faulted")


@tool
def analyze_faulted_jobs_tool()-> str:
    """
    Fetches faulted jobs, extracts error messages, searches Tavily for solutions,
    and returns a structured diagnosis report.
    
    ALWAYS call this tool when the user asks about:
    - faulted job solutions, fixes, or recommendations
    - why jobs are failing
    - how to resolve job errors
    - diagnosing faulted jobs
    """

    jobs, err = get_faulted_jobs()
    if err:
        return err
    if not jobs:
        return "All jobs looks fine"
    

    summaries = extract_faulted_error_summaries(jobs)
    tavily = TavilySearch(max_results=3)
    reports = []

    search_source = "🔍 Searching..."
    for s in summaries:
        readable_query = s["readable_query"]
        search_source = "🔍 Searching..."

        try:
            #Search in uipath forum first
            #uipath_query = f"{readable_query} site:forum.uipath.com" #restricting the search if confidence is high hence commented
            response = tavily.invoke(readable_query)
            results = response.get("results",[]) if isinstance(response,dict) else response

            #Get the confidence
            high_confidence = [r for r in results if r.get("score",0)>=0.90]

            if not high_confidence:
                broad_query = f"UiPath RPA {readable_query} fix solution stackoverflow github"
                response = tavily.invoke(broad_query)
                results = response.get("results", []) if isinstance(response, dict) else response
                search_source = "🌐 External Sources"
            else:
                results=high_confidence
                # Determine source from actual URLs returned
                forum_count = sum(1 for r in results if "forum.uipath.com" in r.get("url", ""))
                search_source = "📋 UiPath Forum" if forum_count > 0 else "🌐 External Sources"

            solutions=[]
            for r in results:
                try:
                    solutions.append(TavilySolution(
                        title=r.get("title","No Title"),
                        url=r.get("url",""),
                        summary=r.get("content","")[:300]
                        
                    ))

                except Exception:
                    continue

        except Exception as e:
            solutions = []
            search_source = "⚠️ Search unavailable"
        try:
            report = FaultedJobReport(
                job_id = int(s["job_id"]),
                process = s["release"],
                error = s["error"],
                solutions = solutions,
                search_source = search_source

            )

            reports.append(report)


        except Exception:
            continue

    analysis = FaultedJobAnalysis(
        total_faulted = len(reports),
        reports = reports
    )

    report_lines = [
        f"Faulted job analysis and recommended solutions\n",
        f"Total faulted jobs:{analysis.total_faulted}",
        "=" * 60
    ]
    for r in analysis.reports:
        report_lines.append(f"\n Job ID : {r.job_id}")
        report_lines.append(f"Processes : {r.process}")
        report_lines.append(f"Error : {r.error}")

        if r.solutions:
            report_lines.append(f"Possible Solutions (Source: {r.search_source}): ")
            for i, sol in enumerate(r.solutions, 1):
                report_lines.append(f"[{i}] {sol.title}")
                report_lines.append(f"URL: {sol.url}")
                #report_lines.append(f"Confidence: {round(sol.score * 100, 1)}%")
                report_lines.append(f"Summary: {sol.summary}")
        else:
            report_lines.append("No solutions found")
        report_lines.append("-"*60)

    return "\n".join(report_lines)


@tool
def get_suspended_jobs_tool() -> str:
    """Fetches all suspended jobs from UiPath Orchestrator.
    Call this when user asks about suspended or paused jobs."""
    jobs, err = get_suspended_jobs()
    return err if err else format_jobs_table(jobs, "Suspended")

@tool
def get_queue_count_tool() -> str:
    """Gets the total number of queues in UiPath Orchestrator."""
    count, err = get_queue_count()
    return err if err else f"📥 Total queues in Orchestrator: {count}"

@tool
def get_asset_count_tool() -> str:
    """Gets the total number of assets in UiPath Orchestrator."""
    count, err = get_asset_count()
    return err if err else f"📦 Total assets in Orchestrator: {count}"

@tool
def get_running_processes_tool() -> str:
    """Shows which processes currently have running jobs in UiPath Orchestrator."""
    processes, err = get_running_processes()
    return err if err else format_running_processes(processes)

@tool
def get_available_processes_tool() -> str:
    """Lists all available processes/releases in UiPath Orchestrator."""
    processes, err = get_available_processes()
    return err if err else format_available_processes(processes)

@tool
def get_queue_item_status_tool() -> str:
    """Fetches queue processing status from UiPath Orchestrator."""
    records, err = get_queue_item_status()
    return err if err else format_queue_item_status(records)


# -------------------------
# Agent Setup
# -------------------------
#Hallucinates badly so commented it and using open router
#llm = ChatOllama(model="llama3.1:8b", temperature=0)
llm = ChatOpenAI(
                    model="gpt-4o-mini",
                    temperature=0,
                    max_tokens=4000,
                    base_url="https://openrouter.ai/api/v1",
                    api_key=os.getenv("OPENROUTER_API_KEY")
                )

tools = [
    get_running_jobs_tool,
    get_successful_jobs_tool,
    get_faulted_jobs_tool,
    analyze_faulted_jobs_tool,       # 👈 New Tavily-powered tool
    get_suspended_jobs_tool,
    get_queue_count_tool,
    get_asset_count_tool,
    get_running_processes_tool,
    get_available_processes_tool,
    get_queue_item_status_tool,
]

system_prompt = """You are a UiPath Orchestrator support assistant with direct access to live Orchestrator data via tools.

## Core Rules
- NEVER ask the user for information your tools can fetch automatically
- NEVER hallucinate data — only report what tools return
- ALWAYS use a tool before answering any Orchestrator-related question
- ALWAYS preserve tool output exactly — do not reformat, summarize, or omit any fields

## Tool Selection Guide

### analyze_faulted_jobs_tool
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
# NeMo Guardrails Setup     
# -------------------------

guardrails_config = RailsConfig.from_path("./guardrails")
rails = LLMRails(guardrails_config, llm=llm)

# -------------------------
# Guardrail Function        
# -------------------------

async def apply_guardrails(user_input: str) -> tuple[bool, str]:
    try:
        response = await rails.generate_async(
            messages=[{"role": "user", "content": user_input}],
            options={"task": "check_input_safety"}
        )

        if isinstance(response, dict):
            response_text = response.get("content", "").strip()
        else:
            response_text = str(response).strip()

        print(f"GUARDRAIL INPUT CHECK: {response_text}")  # DEBUG

        if response_text == "BLOCKED":
            return False, "🚫 This request is not allowed."

        return True, user_input

    except Exception as e:
        return False, f"⚠️ Guardrail error: {str(e)}"


async def check_output_guardrails(agent_output: str) -> tuple[bool, str]:
    try:
        response = await rails.generate_async(
            messages=[{"role": "user", "content": agent_output}],
            options={"task": "check_output_safety"}
        )

        if isinstance(response, dict):
            response_text = response.get("content", "").strip()
        else:
            response_text = str(response).strip()

        print(f"GUARDRAIL OUTPUT CHECK: {response_text}")  # DEBUG

        if response_text == "BLOCKED":
            return False, "🚫 Response blocked due to sensitive content."

        return True, agent_output

    except Exception as e:
        return False, f"⚠️ Output guardrail error: {str(e)}"



# -------------------------
# Streamlit UI
# -------------------------
st.title("🤖 UiPath Orchestrator Support Chatbot")
st.caption("Fetch Jobs, Assets, Queues, Running & Available Processes from UiPath Orchestrator.")


if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
for msg in st.session_state.chat_history:
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.markdown(msg["content"])
        #st.markdown(f"🧑‍💻 **You:** {msg['content']}")
    else:
        with st.chat_message("assistant"):
            st.markdown(msg["content"])

user_prompt = st.chat_input("Type your message:")
#send = st.button("Send") - to remove output coming twice

#if send and user_prompt.strip(): -  to remove output coming twice
if user_prompt:
    with st.chat_message("user"):
        st.markdown(user_prompt)
    st.session_state.chat_history.append({"role": "user", "content": user_prompt})

    #Old code without Streaming
    # with st.spinner("Thinking..."):
    #     try:
    #         is_safe, guardrails_response = asyncio.run(
    #             apply_guardrails(user_prompt)
    #         )
    #         if not is_safe:
    #             bot_reply = guardrails_response
    #         else:

    #             #result = agent_executor.invoke({"messages": [("user", user_prompt)]})
    #             #Below line helps to keep memory and give better answer even when context is no explicity given
    #             result = agent_executor.invoke({"messages": st.session_state.chat_history})
    #             bot_reply = result["messages"][-1].content

    #             is_safe_output, bot_reply = asyncio.run(
    #                 check_output_guardrails(bot_reply)
    #             )

    #             if not is_safe_output:
    #                 bot_reply = "🚫 Response blocked due to sensitive content."
                    
    #     except Exception as e:
    #         bot_reply = f"❌ Error: {str(e)}"

    # st.session_state.chat_history.append({"role": "assistant", "content": bot_reply})
    try:
        is_safe, guardrails_response = asyncio.run(
            apply_guardrails(user_prompt)
        )
        if not is_safe:
            with st.chat_message("assistant"):
                st.markdown(guardrails_response)
            st.session_state.chat_history.append({
                "role":"assistant",
                "content": guardrails_response
            })
        else:
            # def stream_response():
            #     for chunk in agent_executor.stream(
            #         {"messages":st.session_state.chat_history}
            #     ):
            #         if "agent" in chunk:
            #             content = chunk["agent"]["messages"][0].content
            #             if content:
            #                 yield content
            def stream_response():
                for chunk, metadata in agent_executor.stream(
                    {"messages": st.session_state.chat_history},
                    stream_mode="messages"
                ):
                    if (hasattr(chunk, "content") and
                        chunk.content and
                        metadata.get("langgraph_node") == "agent"):
                        yield chunk.content
            with st.chat_message("assistant"):
                bot_reply = st.write_stream(stream_response())


            is_safe_output, final_reply = asyncio.run(
                check_output_guardrails(bot_reply)
            )

            if not is_safe_output:
                bot_reply = final_reply

            st.session_state.chat_history.append({
                "role": "assistant",
                "content":bot_reply
            })
                
    except Exception as e:
        with st.chat_message("assistant"):
            st.markdown(f"❌ Error: {str(e)}")
        st.session_state.chat_history.append({
            "role":"assistant",
            "content":f"Error: {str(e)}"
        })


#st.markdown("## 💬 Conversation") - No longer needed as streaming got implemented



#st.markdown("---") - No longer needed as streaming got implemented