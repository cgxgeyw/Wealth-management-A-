from fastapi import APIRouter

from app.schemas.modules import ModuleItem, ModuleListResponse

router = APIRouter()


@router.get("", response_model=ModuleListResponse)
def list_modules() -> ModuleListResponse:
    modules = [
        ModuleItem(key="data_sources", name="数据源管理", status="mvp"),
        ModuleItem(key="data_analysis", name="数据分析", status="mvp"),
        ModuleItem(key="knowledge_base", name="知识库", status="mvp"),
        ModuleItem(key="agents", name="Agent 管理", status="mvp"),
        ModuleItem(key="analysis_tasks", name="分析任务", status="mvp"),
    ]
    return ModuleListResponse(items=modules)
