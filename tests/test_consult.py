import json
import os
import sys
import unittest
from datetime import datetime
from dotenv import load_dotenv

# Add the project root to the path to allow importing modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ml_serving.ai_service import consult


class TestConsult(unittest.TestCase):
    """Test class for testing the consult functionality"""

    def setUp(self):
        """Setup test environment"""
        # Load environment variables
        load_dotenv()
        self.test_file = os.path.join(os.path.dirname(__file__), "SMCI_2025-03-23.yaml")

    def test_consult_basic(self):
        """Test that the consult function returns valid results"""
        result = consult(self.test_file, backend="lmstudio")
        self.assertIsInstance(result, dict)
        # Check for required fields in the response
        expected_fields = ["symbol", "rating", "confidence", "reasoning", 
                           "enter_strategy", "exit_strategy"]
        for field in expected_fields:
            self.assertIn(field, result, f"Missing field: {field}")

    def test_consult_different_prompts(self):
        """Test consult with different prompt versions"""
        for version in [3, 4, 5]:
            with self.subTest(prompt_version=version):
                result = consult(self.test_file, backend="lmstudio")
                self.assertIsInstance(result, dict)
                # At minimum, there should be a rating
                self.assertIn("rating", result)


def test_consult():
    """
    Stand-alone test function to demonstrate the use of the consult function with sample data
    Can be run directly without unittest framework
    """
    start_time = datetime.now()
    print(f"Starting stock analysis test at: {start_time}")

    # Get the path to the test file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    test_file = os.path.join(current_dir, "SMCI_2025-03-23.yaml")
    result = consult(test_file, backend="lmstudio", model="fino1-14b-mlx")

    if result:
        print(f"Analysis result: {json.dumps(result, indent=2)}")
    else:
        print("Analysis failed to produce a valid result")

    end_time = datetime.now()
    print(f"Test completed in: {end_time - start_time}")

    return result


if __name__ == "__main__":
    # If run directly, perform the stand-alone test
    test_consult()
    
    # To run the unittest suite, comment the above and uncomment below
    # unittest.main()
