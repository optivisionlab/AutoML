#!/bin/bash

# Script to run API test for algorithm comparison

echo "========================================================================"
echo "ALGORITHM COMPARISON TEST VIA API"
echo "========================================================================"
echo ""

# Activate conda environment
echo "Activating conda environment HAutoML..."
source ~/miniconda3/etc/profile.d/conda.sh
conda activate HAutoML

echo ""
echo "Checking if API is running..."
if curl -s http://localhost:9999/docs > /dev/null 2>&1; then
    echo "✅ API is running"
else
    echo "❌ API is not running"
    echo ""
    echo "Please start the API first:"
    echo "  docker run --name hautoml_toolkit_v1 --network host --env-file temp.env hautoml-toolkit python app.py"
    echo ""
    echo "Or use docker-compose:"
    echo "  docker-compose up -d hautoml_toolkit"
    exit 1
fi

echo ""
echo "Running API test..."
echo ""

python test_algorithms_api.py

echo ""
echo "Test completed!"
