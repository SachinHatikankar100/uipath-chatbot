from langchain_tavily import TavilySearch
import os
os.environ["TAVILY_API_KEY"] = "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"

tavily = TavilySearch(max_results=2)
print(tavily.invoke("UiPath faulted job error 1/0 is not valid"))