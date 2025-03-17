import sys
import os
import time

# Add project root to path if running directly
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import the function to test
from ml_serving.ollama_summarize import ollama_summarize

def main():
    text = """
Should You Forget Palantir and Buy These 2 Artificial Intelligence (AI) Stocks Instead?
March 08, 2025 — 04:35 am EST
Written by Geoffrey Seiler for The Motley Fool->
While it's well off its recent highs, Palantir Technologies (NASDAQ: PLTR) was one of the best-performing stocks in 2024 and early 2025. However, those gains have led to an extreme valuation, with the stock trading at a forward price-to-sales (P/S) multiple of 52 times 2025 analyst revenue estimates.
The company has been seeing accelerating revenue growth, with revenue climbing 36% last quarter, led by a 64% jump in U.S. commercial revenue. The company's success stems from its focus on the application and workflow layers of artificial intelligence (AI). Palantir aims to become an AI operating system for its users, creating a platform that can help organizations run AI applications in a real-world environment. It has been highly successful in bringing in new commercial customers through its use of AI boot camps to train and onboard customers, and now it has a big opportunity as it moves these customers from proof-of-concept work into production.
Start Your Mornings Smarter! Wake up with Breakfast news in your inbox every market day. Sign Up For Free »
However, the company is very closely tied to the U.S. government, its largest customer which accounted for more than 40% of its revenue in the fourth quarter, and the government is currently undergoing massive cost-saving measures and slashing budgets. This includes the White House telling the Department of Defense to reduce its budget by 8% a year over the next five years. It's unknown whether Palantir will be helped or hurt by these DOD budget cuts, but it's a big risk.
Given its very high valuation and the risks associated with its largest customer, let's look at two alternative cheaper software AI names to consider.
Salesforce
Salesforce (NYSE: CRM) is known as the leader in customer relationship management (CRM) software. Through the acquisitions of Mulesoft, Tableau, and Slack in recent years it has also gotten into the areas of automation, analytics, and employee communication. The company has always been at the forefront of innovation, being one of the first companies to adopt the software-as-a-service (SaaS) model, which revolutionized the entire software industry.
Salesforce hopes to be a leader in the next evolution of AI, called agentic AI. Much of the early focus on AI has been on what is known as generative AI, where AI will create content, whether it be text, images, or video, based on user prompts. An example of this is using ChatGPT to help plan a wedding. ChatGPT can create a plan, including a task list, based on user inputs. Agentic AI goes beyond generative AI by going out and autonomously completing tasks with little human intervention. So in the case of planning a wedding, it could also rent the venue, hire the caterer and other vendors, and execute other necessary tasks.
Salesforce is looking to be the leader in agentic AI with its Agentforce solution. The agentic AI platform offers a number of out-of-the-box AI agents and allows customers to build and customize their own AI agents using its no-code and low-code tools. The company says the AI agents can be equipped with any business knowledge in order to fill their role and complete necessary tasks while having guardrails of what the agents can and cannot do.
Thus far, Agentforce has drawn a lot of interest from customers, with Salesforce saying it has 5,000 Agentforce deals (including 3,000 paying deals) since it was launched in October. Agentforce is a consumption product that costs $2 per conversation, so the upside for Salesforce is absolutely huge if it can prove its solution saves its customers money. It has also recently introduced AgentExchange, which includes 200 initial partners, including companies like Alphabet and Workday, and hundreds of ready-made app actions, integrations, and templates. This should help expand use cases and foster adoption.
Meanwhile, the stock is reasonably priced, trading at a forward price-to-sales (P/S) multiple under 7 and a forward price-to-earnings (P/E) ratio of 26.
The letters AI within a brain shape.
SentinelOne
SentinelOne (NYSE: S) is a fast-growing AI-powered cybersecurity company that has a nice catalyst ahead of it later this year. The company is focused on endpoint security, which is the protection of a network and its endpoints, such as smartphones and computers. Its main offering is its Singularity Platform, which uses AI to predict, monitor, and eliminate threats.
The company competes with CrowdStrike (NASDAQ: CRWD) and has been looking to take advantage of its larger competitor's earlier outage that caused a lot of disruption. Its platform ranks highly in the Gartner Magic Quadrant for Endpoint Protection Platforms but trails CrowdStrike. However, one of its big selling points is that SentinelOne can automatically roll back any changes to return a client's system to where it was before an attack occurred, eliminating the time-consuming, manual fix that some CrowdStrike customers dealt with after its outage. Last quarter, the company said it saw a record number of competitive wins versus CrowdStrike, and a Fortune 50 company switched to its platform.
Meanwhile, SentinelOne is seeing huge success upselling its Purple AI solution, which helps analysts hunt complex security threats through the use of natural language prompts. It said it is the fastest-growing platform in its history.
Importantly, though, the company has a big catalyst later this year when enterprise PC vendor Lenovo will begin shipping all its PCs with SentinelOne's Singularity Platform on them. The two companies are also developing a new managed detection and response (MDR) service using AI and endpoint detection and response (EDR) capabilities based on the Singularity Platform. Lenovo is the world's largest PC vendor, selling nearly 62 million units in 2024, so this is a big opportunity for SentinelOne.
At the same time, the stock is attractively priced, trading at a P/E ratio of under 5 times fiscal 2026 analyst estimates.
"""
    print("Running ollama_summarize test...")
    try:
        # Start the timer
        start_time = time.time()
        
        summary = ollama_summarize(text)
        
        # Calculate and display elapsed time
        elapsed_time = time.time() - start_time
        print(f"\nOllama summarization completed in {elapsed_time:.2f} seconds")
        
        print("\nSummary results:")
        print(f"Title: {summary.get('title', 'N/A')}")
        print(f"Summary: {summary.get('summary', 'N/A')}")
        
        # Print stock details if available
        stocks = summary.get('stocks', [])
        if stocks:
            print("\nStocks mentioned:")
            for stock in stocks:
                print(f"- {stock.get('ticker', 'N/A')}: {stock.get('name', 'N/A')}")
                print(f"  Pros: {', '.join(stock.get('pros', []))}")
                print(f"  Cons: {', '.join(stock.get('cons', []))}")
        
        print("\nTest completed successfully!")
        return summary
    except Exception as e:
        print(f"\nError in ollama_summarize: {e}")
        return None


if __name__ == "__main__":
    main()