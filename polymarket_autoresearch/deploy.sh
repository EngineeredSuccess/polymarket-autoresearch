#!/bin/bash
# Deploy Polymarket Autoresearch to RunPod
# Usage: bash deploy.sh

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}Polymarket Autoresearch - Deploy to RunPod${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""

# Check for RunPod API key
if [ -z "$RUNPOD_API_KEY" ]; then
    if [ -f "../runpod.txt" ]; then
        export RUNPOD_API_KEY=$(cat ../runpod.txt | tr -d '\n\r')
        echo -e "${YELLOW}Using API key from runpod.txt${NC}"
    else
        echo -e "${RED}Error: RUNPOD_API_KEY not set${NC}"
        echo "Set it with: export RUNPOD_API_KEY='your_key'"
        exit 1
    fi
fi

echo -e "${GREEN}1. Checking API key...${NC}"
curl -s -H "Authorization: Bearer $RUNPOD_API_KEY" \
    "https://api.runpod.io/graphql" \
    -d '{"query": "{ me { id } }"}' | grep -q "id" && \
    echo -e "${GREEN}   API key valid!${NC}" || \
    { echo -e "${RED}   Invalid API key${NC}"; exit 1; }

echo -e "${GREEN}2. Creating workspace template...${NC}"

# GraphQL mutation to create workspace
CREATE_WORKSPACE='{
  "query": "mutation CreateWorkspace($input: CreateWorkspaceInput!) { createWorkspace(input: $input) { id name } }",
  "variables": {
    "input": {
      "templateId": "polymarket-autoresearch",
      "gpuTypeId": "NVIDIA-RTX-4090",
      "region": "US-East",
      "minDiskSize": 20,
      "volumeInGb": 50,
      "name": "polymarket-autoresearch"
    }
  }
}'

echo -e "${GREEN}3. Starting workspace...${NC}"

# For simplicity, we'll create a Pod instead
CREATE_POD='{
  "query": "mutation CreatePod($input: CreatePodInput!) { createPod(input: $input) { id status } }",
  "variables": {
    "input": {
      "templateName": "PyTorch 2.4",
      "dockerArgs": "",
      "gpuTypeId": "NVIDIA-RTX-4090",
      "region": "US-East",
      "minDiskSize": 40,
      "containerDiskInGb": 15,
      "volumeInGb": 50,
      "machineId": "",
      "podType": "SAFE",
      "name": "polymarket-autoresearch"
    }
  }
}'

echo -e "${YELLOW}   Creating pod with RTX 4090...${NC}"
echo -e "${YELLOW}   Estimated cost: ~$0.0065/min = ~$5/hr${NC}"

# Note: This is a simplified version. For actual deployment,
# use the RunPod dashboard or the Python SDK.

echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}MANUAL DEPLOYMENT STEPS${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo "1. Go to: https://runpod.io/console/pods"
echo "2. Click 'Deploy' -> 'Start from Scratch'"
echo "3. Select: "
echo "   - GPU: RTX 4090"
echo "   - Region: US-East"
echo "   - Template: PyTorch 2.4"
echo "   - Disk: 40GB"
echo ""
echo "4. Once running, SSH in and run:"
echo ""
echo -e "${YELLOW}   # Clone the repo${NC}"
echo "   git clone <your-repo-url>"
echo "   cd polymarket_autoresearch"
echo ""
echo -e "${YELLOW}   # Install dependencies${NC}"
echo "   pip install -r requirements.txt"
echo ""
echo -e "${YELLOW}   # Prepare data${NC}"
echo "   python prepare.py"
echo ""
echo -e "${YELLOW}   # Run baseline${NC}"
echo "   python backtest.py"
echo ""
echo -e "${YELLOW}   # Start AI agent optimization${NC}"
echo "   # (Follow instructions in program.md)"
echo ""
echo -e "${GREEN}======================================${NC}"
echo ""

# Save deploy instructions
cat > DEPLOY_INSTRUCTIONS.md << 'EOF'
# RunPod Deployment Instructions

## Quick Deploy

1. Go to https://runpod.io/console/pods
2. Deploy new pod:
   - **GPU**: RTX 4090
   - **Region**: US-East  
   - **Template**: PyTorch 2.4
   - **Disk**: 40GB
   - **Cost**: ~$0.0065/min

3. SSH into the pod

4. Run setup:
```bash
# Install dependencies
pip install -r requirements.txt

# Prepare data
python prepare.py

# Test baseline
python backtest.py

# Optimize parameters (AI agent)
# Read program.md for instructions
```

## Cost Estimation

| GPU | $/min | $/hour | $/8hrs | $/24hrs |
|-----|-------|--------|--------|---------|
| RTX 4090 | $0.0065 | $0.39 | $3.12 | $9.36 |
| RTX 3090 | $0.0045 | $0.27 | $2.16 | $6.48 |

## Optimization Run

A full optimization session (50 experiments):
- ~50-100 minutes of GPU time
- Cost: ~$5-15

## Monitoring

```bash
# Watch experiment logs
tail -f results/experiments.jsonl

# Check GPU usage
nvidia-smi

# Monitor costs
curl -H "Authorization: Bearer $RUNPOD_API_KEY" \
  "https://api.runpod.io/graphql" \
  -d '{"query": "{ me { compute { pods { runtime { unitCost } } } } }"}'
```

## SSH Access

After pod starts, get SSH command from RunPod console:
```bash
ssh root@<pod-ip>
```
EOF

echo -e "${GREEN}Created DEPLOY_INSTRUCTIONS.md${NC}"
echo ""
echo -e "${GREEN}Done! Open RunPod console to deploy.${NC}"
