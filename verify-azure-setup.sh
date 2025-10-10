#!/bin/bash

# Azure Pipeline Setup Verification Script
# This script helps verify that all required files are present and properly configured

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "           Azure Pipeline Setup Verification"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if required files exist
echo "📋 Checking required files..."
echo ""

files_to_check=(
    "azure-pipelines.yml"
    "README_AZURE.md"
    "AZURE_QUICKSTART.md"
    "AZURE_PIPELINE_SETUP.md"
    "AZURE_ARCHITECTURE.md"
)

all_files_present=true

for file in "${files_to_check[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✅ $file"
    else
        echo "  ❌ $file (MISSING)"
        all_files_present=false
    fi
done

echo ""

if [ "$all_files_present" = false ]; then
    echo "❌ Some required files are missing!"
    echo "   Please ensure all Azure Pipeline files are present."
    exit 1
fi

# Validate YAML syntax if Python is available
echo "🔍 Validating YAML syntax..."
echo ""

if command -v python3 &> /dev/null; then
    if python3 -c "import yaml" 2>/dev/null; then
        if python3 -c "import yaml; yaml.safe_load(open('azure-pipelines.yml'))" 2>/dev/null; then
            echo "  ✅ azure-pipelines.yml syntax is valid"
        else
            echo "  ❌ azure-pipelines.yml has syntax errors"
            exit 1
        fi
    else
        echo "  ⚠️  PyYAML not installed, skipping YAML validation"
        echo "     Install with: pip install pyyaml"
    fi
else
    echo "  ⚠️  Python not found, skipping YAML validation"
fi

echo ""

# Check YAML configuration
echo "⚙️  Checking YAML configuration..."
echo ""

# Check if master branch is configured in trigger
if grep -q "master" azure-pipelines.yml; then
    echo "  ✅ Trigger configured for master branch"
else
    echo "  ⚠️  Master branch not found in triggers"
fi

# Check if AzureDevOpsRepoUrl variable is referenced
if grep -q "AzureDevOpsRepoUrl" azure-pipelines.yml; then
    echo "  ✅ AzureDevOpsRepoUrl variable referenced"
else
    echo "  ❌ AzureDevOpsRepoUrl variable not found"
fi

# Check if System.AccessToken is used
if grep -q "System.AccessToken" azure-pipelines.yml; then
    echo "  ✅ OAuth authentication configured"
else
    echo "  ⚠️  System.AccessToken not found"
fi

echo ""

# Display documentation guide
echo "📚 Documentation Guide:"
echo ""
echo "  1. Start Here:     README_AZURE.md          (Overview & Index)"
echo "  2. Quick Setup:    AZURE_QUICKSTART.md      (5-minute guide)"
echo "  3. Full Setup:     AZURE_PIPELINE_SETUP.md  (Complete documentation)"
echo "  4. Architecture:   AZURE_ARCHITECTURE.md    (Technical details)"
echo "  5. Configuration:  azure-pipelines.yml      (YAML config)"
echo ""

# Display next steps
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "                        🚀 Next Steps"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. Read the Quick Start Guide:"
echo "   cat AZURE_QUICKSTART.md"
echo ""
echo "2. Get your Azure DevOps repository URL:"
echo "   Format: https://dev.azure.com/{organization}/{project}/_git/{repository}"
echo ""
echo "3. Import pipeline to Azure DevOps:"
echo "   • Go to Azure DevOps → Pipelines → New Pipeline"
echo "   • Select GitHub as source"
echo "   • Choose this repository"
echo "   • Azure will auto-detect azure-pipelines.yml"
echo ""
echo "4. Configure the AzureDevOpsRepoUrl variable in Azure DevOps"
echo ""
echo "5. Set up permissions as described in AZURE_PIPELINE_SETUP.md"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ "$all_files_present" = true ]; then
    echo "✅ All required files are present and basic checks passed!"
    echo ""
    echo "You're ready to set up the Azure Pipeline!"
    echo "Start with: cat AZURE_QUICKSTART.md"
    echo ""
    exit 0
else
    echo "❌ Setup verification failed"
    exit 1
fi
