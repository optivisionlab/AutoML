#!/bin/bash
# Script tự động test các thuật toán

echo "=========================================="
echo "  AutoML Algorithm Testing Suite"
echo "=========================================="
echo ""

# Test all algorithms
echo "1. Running full test suite..."
conda run -n HAutoML python test_algorithms.py

echo ""
echo "=========================================="
echo "2. Testing consistency (3 runs)..."
echo "=========================================="

for i in {1..3}; do
  echo ""
  echo "--- Run $i ---"
  conda run -n HAutoML python test_algorithms.py 2>&1 | grep -A 2 "Best Parameters"
done

echo ""
echo "=========================================="
echo "3. Individual algorithm tests"
echo "=========================================="

echo ""
echo "--- Grid Search ---"
conda run -n HAutoML python test_single_algorithm.py grid 2>&1 | tail -20

echo ""
echo "--- Bayesian Search ---"
conda run -n HAutoML python test_single_algorithm.py bayesian 2>&1 | tail -20

echo ""
echo "--- Genetic Algorithm ---"
conda run -n HAutoML python test_single_algorithm.py genetic 2>&1 | tail -20

echo ""
echo "=========================================="
echo "All tests completed!"
echo "=========================================="
