#!/bin/bash
# Example usage of the Work Request exemption list feature

echo "=== Work Request Exemption List Examples ==="
echo ""

echo "Example 1: Exempt specific Work Requests"
echo "Edit exemption_list.json:"
cat << 'JSON'
{
  "exempted_work_requests": [
    "90093002",
    "89954686"
  ]
}
JSON
echo ""

echo "Example 2: Use custom exemption list file"
echo "Command:"
echo "EXEMPTION_LIST_PATH=/path/to/custom.json python generate_weekly_pdfs.py"
echo ""

echo "Example 3: Different exemption lists for different environments"
echo "Production:"
echo "EXEMPTION_LIST_PATH=exemption_list.prod.json python generate_weekly_pdfs.py"
echo ""
echo "Testing:"
echo "EXEMPTION_LIST_PATH=exemption_list.test.json TEST_MODE=true python generate_weekly_pdfs.py"
echo ""

echo "For full documentation, see: EXEMPTION_LIST.md"
