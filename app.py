import os
import requests
import streamlit as st
from dotenv import load_dotenv
from tabulate import tabulate
from langchain.tools import tool
from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage



# -------------------------
# Load ENV
# -------------------------
load_dotenv()

UIPATH_ACCESS_TOKEN = os.getenv("UIPATH_ACCESS_TOKEN")
UIPATH_ORG = os.getenv("UIPATH_ORG")
UIPATH_TENANT = os.getenv("UIPATH_TENANT")

st.set_page_config(page_title="UiPath Orchestrator Support Chatbot", page_icon="🤖", layout="wide")

if not UIPATH_ACCESS_TOKEN:
    st.error("Missing UIPATH_ACCESS_TOKEN in .env")
    st.stop()

if not UIPATH_ORG or not UIPATH_TENANT:
    st.error("Missing UIPATH_ORG or UIPATH_TENANT in .env")
    st.stop()

BASE_URL = f"https://cloud.uipath.com/{UIPATH_ORG}/{UIPATH_TENANT}/orchestrator_"

HEADERS = {
    "Authorization": f"Bearer {UIPATH_ACCESS_TOKEN}",
    "X-UIPATH-TenantName": UIPATH_TENANT,
    "Content-Type": "application/json",
    "X-UIPATH-OrganizationUnitId": os.getenv("UIPATH_FOLDER_ID")
}

# -------------------------
# API Helpers
# -------------------------
def call_orchestrator(url: str):
    response = requests.get(url, headers=HEADERS)

    if response.status_code != 200:
        return None, f"❌ API failed | {response.status_code} | {response.text}"

    return response.json(), None


def call_orchestrator_count(url: str):
    response = requests.get(url, headers=HEADERS)

    if response.status_code != 200:
        return None, f"❌ API failed | {response.status_code} | {response.text}"

    data = response.json()
    count = data.get("@odata.count")
    return count, None


# -------------------------
# JOBS - different states
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

    table = tabulate(pretty_jobs, headers="keys", tablefmt="fancy_grid")
    return f"📌 Jobs in state: {state}\n\n{table}"


def get_jobs_by_state(state: str):
    url = f"{BASE_URL}/odata/Jobs?$filter=State eq '{state}'"
    data, err = call_orchestrator(url)

    if err:
        return None, err

    jobs = data.get("value", [])
    return jobs, None


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
    
    # Get queue names
    names_url = f"{BASE_URL}/odata/QueueDefinitions?$select=Id,Name"
    names_data, err = call_orchestrator(names_url)
    if err:
        return None, err
    
    # Build a lookup map: {id: name}
    name_map = {q["Id"]: q["Name"] for q in names_data.get("value", [])}

    # Attach name to each record
    records = data.get("value", [])
    for r in records:
        r["QueueName"] = name_map.get(r.get("QueueDefinitionId"), "Unknown")

    return records, None



# -------------------------
# RUNNING PROCESSES
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


# -------------------------
# AVAILABLE PROCESSES
# -------------------------
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

    rows = []
    for name, count in sorted(process_map.items(), key=lambda x: x[1], reverse=True):
        rows.append({
            "Process Name": name,
            "Running Jobs": count
        })

    table = tabulate(rows, headers="keys", tablefmt="fancy_grid")
    return f"🟢 Running Processes\n\n{table}"


def format_available_processes(processes):
    if not processes:
        return "⚠️ No processes found in Orchestrator."

    rows = []
    for p in processes:
        rows.append({
            "Name": p.get("Name"),
            "ProcessKey": p.get("ProcessKey"),
            "EnvironmentId": p.get("EnvironmentId")
        })

    table = tabulate(rows, headers="keys", tablefmt="fancy_grid")
    return f"📦 Available Processes ({len(processes)})\n\n{table}"

def format_queue_item_status(records):
    if not records:
        return "⚠️ No queue processing records found."

    rows = []
    for r in records:
        rows.append({
            "Queue Name": r.get("QueueName"),
            "Queue ID": r.get("QueueDefinitionId"),
            "Successful": r.get("NumberOfSuccessfulTransactions"),
            "App Exceptions": r.get("NumberOfApplicationExceptions"),
            "Biz Exceptions": r.get("NumberOfBusinessExceptions"),
            "Total": r.get("TotalNumberOfTransactions"),
            "Report Type": r.get("ReportType"),
        })

    table = tabulate(rows, headers="keys", tablefmt="fancy_grid")
    return f"📊 Queue Processing Status ({len(records)} records)\n\n{table}"

# -------------------------
# Adding Tools
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
    """Fetches all failed/faulted jobs from UiPath Orchestrator.
    Call this when user asks about failed jobs, faulted jobs, or job errors."""
    jobs, err = get_faulted_jobs()
    return err if err else format_jobs_table(jobs, "Faulted")

@tool
def get_suspended_jobs_tool() -> str:
    """Fetches all suspended jobs from UiPath Orchestrator.
    Call this when user asks about suspended or paused jobs."""
    jobs, err = get_suspended_jobs()
    return err if err else format_jobs_table(jobs, "Suspended")

@tool
def get_queue_count_tool() -> str:
    """Gets the total number of queues in UiPath Orchestrator.
    Call this when user asks how many queues exist."""
    count, err = get_queue_count()
    return err if err else f"📥 Total queues in Orchestrator: {count}"

@tool
def get_asset_count_tool() -> str:
    """Gets the total number of assets in UiPath Orchestrator.
    Call this when user asks how many assets exist."""
    count, err = get_asset_count()
    return err if err else f"📦 Total assets in Orchestrator: {count}"

@tool
def get_running_processes_tool() -> str:
    """Shows which processes currently have running jobs in UiPath Orchestrator.
    Call this when user asks about running processes or active processes."""
    processes, err = get_running_processes()
    return err if err else format_running_processes(processes)

@tool
def get_available_processes_tool() -> str:
    """Lists all available processes/releases in UiPath Orchestrator.
    Call this when user asks about available processes, all processes, or process list."""
    processes, err = get_available_processes()
    return err if err else format_available_processes(processes)

@tool
def get_queue_item_status_tool() -> str:
    """Fetches queue processing status from UiPath Orchestrator.
    Call this when user asks about queue status, queue items, queue processing, or queue health."""
    records, err = get_queue_item_status()
    return err if err else format_queue_item_status(records)
# -------------------------
# Intent Detection
# -------------------------
# Initialize Ollama (do this once, outside the if send block)
llm = ChatOllama(model="llama3.1:8b", temperature=0)

tools = [get_running_jobs_tool,
    get_successful_jobs_tool,
    get_faulted_jobs_tool,
    get_suspended_jobs_tool,
    get_queue_count_tool,
    get_asset_count_tool,
    get_running_processes_tool,
    get_available_processes_tool,
    get_queue_item_status_tool]  # all your tools

agent_executor = create_react_agent(llm, tools)


print("Testing API connection...")
test_url = f"{BASE_URL}/odata/Jobs?$top=1"
test_response = requests.get(test_url, headers=HEADERS)
print(f"Status: {test_response.status_code}")
print(f"Response: {test_response.text[:200]}")
# -------------------------
# Streamlit UI
# -------------------------
st.title("🤖 UiPath Orchestrator Support Chatbot")
st.caption("Fetch Jobs, Assets, Queues, Running & Available Processes from UiPath Orchestrator.")

# Store history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Input
user_prompt = st.text_input("Type your message:")
send = st.button("Send")

# Handle prompt
if send and user_prompt.strip():
    st.session_state.chat_history.append({"role": "user", "content": user_prompt})

    with st.spinner("Thinking..."):
        try:
            result = agent_executor.invoke({"messages": [("user", user_prompt)]})
            bot_reply = result["messages"][-1].content
        except Exception as e:
            bot_reply = f"❌ Error: {str(e)}"
       

    st.session_state.chat_history.append({"role": "assistant", "content": bot_reply})

    # Clear input (works in old versions)
    #st.experimental_rerun()

# Display history
st.markdown("## 💬 Conversation")

for msg in st.session_state.chat_history:
    if msg["role"] == "user":
        st.markdown(f"🧑‍💻 **You:** {msg['content']}")
    else:
        st.markdown("🤖 **Bot:**")
        st.code(msg["content"], language="text")

st.markdown("---")