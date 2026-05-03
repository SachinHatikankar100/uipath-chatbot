# @tool
# def analyze_faulted_jobs_tool() -> str:
#     """
#     Fetches faulted jobs, extracts error messages, searches Tavily for solutions,
#     and returns a structured diagnosis report.
    
#     ALWAYS call this tool when the user asks about:
#     - faulted job solutions, fixes, or recommendations
#     - why jobs are failing
#     - how to resolve job errors
#     - diagnosing faulted jobs
#     """
#     jobs, err = get_faulted_jobs()
#     if err:
#         return err
#     if not jobs:
#         return "✅ No faulted jobs found. Everything looks healthy!"

#     summaries = extract_faulted_error_summaries(jobs)
#     tavily = TavilySearch(max_results=3)

#     report_lines = ["🔍 Faulted Job Analysis & Recommended Solutions\n", "=" * 60]

#     for s in summaries:
#         report_lines.append(f"\n📌 Job ID    : {s['job_id']}")
#         report_lines.append(f"   Process   : {s['release']}")
#         report_lines.append(f"   Error     : {s['error']}")
#         report_lines.append(f"   Searching : {s['search_query'][:100]}...")

#         try:
#             response = tavily.invoke(s["search_query"])
#             #add to resolve the bug
#             results = response.get("results",[]) if isinstance(response,dict) else response

#             if results:
#                 report_lines.append("   💡 Possible Solutions:")
#                 for i, r in enumerate(results[:3], 1):
#                     title = r.get("title", "No title")
#                     url = r.get("url", "")
#                     content = r.get("content", "")[:300]  # trim long snippets
#                     report_lines.append(f"      [{i}] {title}")
#                     report_lines.append(f"          🔗 {url}")
#                     report_lines.append(f"          📝 {content}...")
#             else:
#                 report_lines.append("   ⚠️ No relevant solutions found online.")

#         except Exception as e:
#             report_lines.append(f"   ❌ Tavily search failed: {str(e)}")

#         report_lines.append("-" * 60)

#     return "\n".join(report_lines)
