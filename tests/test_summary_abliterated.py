import unittest
from langchain.schema import Document
from dotenv import load_dotenv
import os
import sys

# Add the project root to the path to allow importing modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ml_serving.ai_service import map_reduce_summarize_stock

class TestMapReduceSummarize(unittest.TestCase):
    """Test class for testing the map_reduce_summarize functionality"""

    def setUp(self):
        """Setup test environment"""
        # Load environment variables
        load_dotenv()
        self.sample_text = """
        Should You Forget Palantir and Buy These 2 Artificial Intelligence (AI) Stocks Instead?
        March 08, 2025 — 04:35 am EST
        Written by Geoffrey Seiler for The Motley Fool->
        While it's well off its recent highs, Palantir Technologies (NASDAQ: PLTR) was one of the best-performing stocks in 2024 and early 2025. However, those gains have led to an extreme valuation, with the stock trading at a forward price-to-sales (P/S) multiple of 52 times 2025 analyst revenue estimates.
        """
        self.documents = [Document(page_content=self.sample_text)]

    def test_basic_summary(self):
        """Test that the map_reduce_summarize function returns a valid summary"""
        result = map_reduce_summarize_stock(
            documents=self.documents,
            stock="TEST",
            backend="lmstudio",
            chunk_size=16000,
            batch_size=4,
        )
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0, "Summary result should not be empty")

    def test_multiple_documents(self):
        """Test map_reduce_summarize with multiple documents"""
        documents = [
            Document(page_content=self.sample_text),
            Document(page_content=self.sample_text)
        ]
        result = map_reduce_summarize_stock(
            documents=documents,
            stock="TEST",
            backend="lmstudio",
            chunk_size=16000,
            batch_size=4,
        )
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0, "Summary result should not be empty")

def test_map_reduce_summarize_standalone():
    """
    Stand-alone test function to demonstrate the use of the map_reduce_summarize function with sample data
    Can be run directly without unittest framework
    """
    sample_text = """
    Should You Forget Palantir and Buy These 2 Artificial Intelligence (AI) Stocks Instead?
    March 08, 2025 — 04:35 am EST
    Written by Geoffrey Seiler for The Motley Fool->
    While it's well off its recent highs, Palantir Technologies (NASDAQ: PLTR) was one of the best-performing stocks in 2024 and early 2025. However, those gains have led to an extreme valuation, with the stock trading at a forward price-to-sales (P/S) multiple of 52 times 2025 analyst revenue estimates.
    """
    documents = [Document(page_content=sample_text)]
    result = map_reduce_summarize_stock(
        documents=documents,
        stock="TEST",
        backend="lmstudio",
        model="glm-4-9b-chat-abliterated",
        chunk_size=16000,
        batch_size=4,
    )
    print("Summary result:")
    print(result)

if __name__ == "__main__":
    # If run directly, perform the stand-alone test
    test_map_reduce_summarize_standalone()
    
    # To run the unittest suite, comment the above and uncomment below
    # unittest.main()
