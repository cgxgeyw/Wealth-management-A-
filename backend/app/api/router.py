from fastapi import APIRouter

from app.api.routes import agent_runs, agent_tools, agents, data_sources, health, market, modules, sectors, stocks

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(modules.router, prefix="/modules", tags=["modules"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(agent_runs.router, prefix="/agent-runs", tags=["agent runs"])
api_router.include_router(agent_tools.router, prefix="/agent-tools", tags=["agent tools"])
api_router.include_router(data_sources.router, prefix="/data", tags=["data sources"])
api_router.include_router(stocks.router, prefix="/stocks", tags=["stocks"])
api_router.include_router(market.router, prefix="/market", tags=["market"])
api_router.include_router(sectors.router, prefix="/sectors", tags=["sectors"])
