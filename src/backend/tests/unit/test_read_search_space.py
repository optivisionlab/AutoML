# Standard Libraries
import unittest
from shared.search_space import (
    CLASSIFICATION_MODELS,
    METRIC_LIST,
)


class TestModelLoader(unittest.TestCase):
    def test_constants_in_memory(self):
        self.assertIsInstance(CLASSIFICATION_MODELS, dict)
        self.assertIsInstance(METRIC_LIST, list)
        self.assertIn("accuracy", METRIC_LIST)
        self.assertEqual(len(CLASSIFICATION_MODELS), 6)

        # Check models content
        self.assertIn("DecisionTreeClassifier", CLASSIFICATION_MODELS)
        self.assertIn("RandomForestClassifier", CLASSIFICATION_MODELS)
        self.assertIsInstance(CLASSIFICATION_MODELS["DecisionTreeClassifier"], list)


if __name__ == "__main__":
    unittest.main()
