#!/bin/bash
# =============================================
# SMC Performance Tracker — Verify Deployment
# Checks health endpoint and displays status
# =============================================

HEALTH_URL="https://web-production-b63af.up.railway.app/api/v1/health"
SETTINGS_URL="https://smc-tracker-railway-2027.vercel.app/settings"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}🏥 SMC Tracker — Deployment Verification${NC}"
echo "========================================="

# Check backend health
echo -e "\n${YELLOW}1. Backend Health Check${NC}"
RESPONSE=$(curl -s ${HEALTH_URL} 2>/dev/null)
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" ${HEALTH_URL} 2>/dev/null)

if [ "$HTTP_CODE" == "200" ]; then
    echo -e "   ${GREEN}✅ Backend is ONLINE (HTTP ${HTTP_CODE})${NC}"
    echo "   Response: ${RESPONSE}"
else
    echo -e "   ${RED}❌ Backend is DOWN (HTTP ${HTTP_CODE})${NC}"
fi

# Check webhook endpoint
echo -e "\n${YELLOW}2. Webhook Endpoint Check${NC}"
WEBHOOK_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    -H "Content-Type: application/json" \
    -d '{"test": true}' \
    "https://web-production-b63af.up.railway.app/api/v1/signal" 2>/dev/null)

if [ "$WEBHOOK_CODE" != "000" ]; then
    echo -e "   ${GREEN}✅ Webhook endpoint reachable (HTTP ${WEBHOOK_CODE})${NC}"
else
    echo -e "   ${RED}❌ Webhook endpoint unreachable${NC}"
fi

# Check git status
echo -e "\n${YELLOW}3. Git Status${NC}"
echo "   Branch: $(git branch --show-current 2>/dev/null || echo 'N/A')"
echo "   Last commit: $(git log --oneline -1 2>/dev/null || echo 'N/A')"
echo "   Remote: $(git remote get-url origin 2>/dev/null || echo 'N/A')"

DIRTY=$(git status --porcelain 2>/dev/null)
if [ -z "$DIRTY" ]; then
    echo -e "   ${GREEN}✅ Working tree is clean${NC}"
else
    echo -e "   ${YELLOW}⚠️  Uncommitted changes:${NC}"
    echo "$DIRTY" | sed 's/^/      /'
fi

echo -e "\n${GREEN}🎯 Verification complete.${NC}"
