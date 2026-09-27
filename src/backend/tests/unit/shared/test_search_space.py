# Standard Libraries
import unittest
from src.shared.search_space import (
    CLASSIFICATION_MODELS,
    CLASSIFICATION_METRIC_LIST,
)


class TestModelLoader(unittest.TestCase):
    def test_constants_in_memory(self):
        self.assertIsInstance(CLASSIFICATION_MODELS, dict)
        self.assertIsInstance(CLASSIFICATION_METRIC_LIST, list)
        self.assertIn("accuracy", CLASSIFICATION_METRIC_LIST)
        self.assertEqual(len(CLASSIFICATION_MODELS), 6)

        # Check models content
        self.assertIn("DecisionTreeClassifier", CLASSIFICATION_MODELS)
        self.assertIn("RandomForestClassifier", CLASSIFICATION_MODELS)
        self.assertIsInstance(CLASSIFICATION_MODELS["DecisionTreeClassifier"], list)


if __name__ == "__main__":
    unittest.main()
