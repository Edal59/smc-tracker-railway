#!/bin/bash
# =============================================
# SMC Performance Tracker — Quick Deploy Script
# Usage: ./scripts/deploy.sh "commit message"
# =============================================

set -e

REMOTE="origin"
BRANCH="main"
HEALTH_URL="https://web-production-b63af.up.railway.app/api/v1/health"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🚀 SMC Tracker — Deploy Script${NC}"
echo "================================"

# Check for commit message
if [ -z "$1" ]; then
    echo -e "${RED}❌ Please provide a commit message${NC}"
    echo "Usage: ./scripts/deploy.sh \"your commit message\""
    exit 1
fi

# Check for uncommitted changes
if [ -z "$(git status --porcelain)" ]; then
    echo -e "${YELLOW}⚠️  No changes to commit${NC}"
    exit 0
fi

# Show what will be committed
echo -e "\n${YELLOW}📋 Changes to deploy:${NC}"
git status --short
echo ""

# Stage, commit, push
echo -e "${GREEN}📦 Staging changes...${NC}"
git add -A

echo -e "${GREEN}💾 Committing: $1${NC}"
git commit -m "$1"

echo -e "${GREEN}🔄 Pushing to ${REMOTE}/${BRANCH}...${NC}"
git push ${REMOTE} ${BRANCH}

echo -e "\n${GREEN}✅ Push complete! Railway auto-deploy triggered.${NC}"
echo -e "${YELLOW}⏳ Deployment usually takes 1-3 minutes.${NC}"

# Wait and check health
echo -e "\n${YELLOW}Waiting 90 seconds for deployment...${NC}"
sleep 90

echo -e "${GREEN}🏥 Checking health endpoint...${NC}"
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" ${HEALTH_URL} 2>/dev/null || echo "000")

if [ "$HEALTH" == "200" ]; then
    echo -e "${GREEN}✅ Deployment verified — server is healthy!${NC}"
    curl -s ${HEALTH_URL} | python3 -m json.tool 2>/dev/null || true
else
    echo -e "${RED}⚠️  Health check returned HTTP ${HEALTH}${NC}"
    echo "Check Railway dashboard for build status."
fi

echo -e "\n${GREEN}🎉 Done!${NC}"
