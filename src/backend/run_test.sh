#!/bin/bash

# Script to run algorithm comparison test in conda environment

echo "Activating conda environment HAutoML..."
source ~/miniconda3/etc/profile.d/conda.sh
conda activate HAutoML

echo ""
echo "Running algorithm comparison test..."
echo ""

python test_algorithms_simple.py
