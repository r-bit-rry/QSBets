# Real-Time News & Sentiment
# Works with: Country code (e.g., site:forbes.com for US, site:ft.com for UK).
# Excludes: ETFs/SPACs.
# Wildcards: Add dividend * policy to catch phrases like "dividend payment policy".
search_prompt_real_time = """("{stock_name}" OR "${stock_symbol}") ("stock performance" OR "earnings forecast") 
("sentiment analysis" OR "price target") 
(site:bloomberg.com OR site:{country}.com/news OR site:reuters.com) 
after:{current_date - 365} -"ETF" -"SPAC" 
("{sector}" OR "{industry}")"""

# Regulatory Filings & Country-Specific Compliance
# Purpose: Focuses on post-IPO legal filings.
# Adjust: Replace SEC with country-specific terms (e.g., "FCA filings" for UK, "ASIC" for Australia).
search_prompt_regulatory = """"{stock_name}" ("SEC filing" OR "{country} regulatory authority") 
("10-K" OR "annual report" OR "insider trading") 
(before:{current_date} AFTER:{ipo_year}) 
-filetype:pdf -forum"""

# Post-IPO Industry/Sector Analysis
# Wildcards: "geo* impact" to include terms like "geopolitical" or "geoeconomic".
search_prompt_industry_analysis = """"{industry} growth trends" ("{stock_name}" OR "competitors in {industry}") 
AFTER:{ipo_year} 
("supply chain risks" OR "geo-political impact" OR "profit margin") -"ETF" 
site:statista.com OR site:mckinsey.com"""

# Social & Forum Sentiment
# Country filters: Use {country}stocks for localized forums (e.g., subreddit:CanadianInvestors).
search_prompt_social_sentiment = """("{stock_symbol}" OR "stock_name") ("bullish" OR "short squeeze") 
site:twitter.com OR (subreddit:stocks OR subreddit:{country}stocks) 
("DD" OR "technical analysis") AFTER:{current_date - 30} -"meme stock"
"""

# Historical Performance Since IPO
# Purpose: Targets structured data (spreadsheets) for historical sector/industry benchmarking.
search_prompt_historical_performance = """"{stock_name} stock price" "{industry} performance" 
(AFTER:{ipo_year} BEFORE:{current_date - 365*5}) 
"year-over-year comparison" -index -speculation 
filetype:xls OR filetype:csv
"""


# Alternative Data & Risk Factors
# Country: Filters government sources (e.g., site:gov.uk) for ESGs.
search_prompt_alternative_data = """"
"{stock_name}" ("carbon footprint" OR "labor practices") 
"impact on {industry}" site:gov.{country} OR site:csrwire.com 
AFTER:{current_date - 180} -"blog" -"opinion"
"""

# Variable Guide
# Placeholder	Example Value	Requires Your Input?
# {stock_name}	"Apple Inc."	✅ Company name
# {stock_symbol}	AAPL	✅ Ticker symbol
# {industry}	"consumer tech"	✅ Industry focus
# {sector}	"technology"	✅ Sector category
# {country}	"US"	✅ HQ country code
# {ipo_year}	1980	✅ IPO year
# {current_date}	2024-08-25	✅ Today’s date
# Wildcard/Exclusion Best Practices:
# Wildcards (*): Use for unknowns (e.g., "dividend * cut" captures "dividend payout cut").
# Exclusions:
# -index -fund removes results about indices/mutual funds.
# -"climate risk" excludes the exact phrase.
# Date Filters: Replace {current_date} dynamically (e.g., use after:2023-08-25).