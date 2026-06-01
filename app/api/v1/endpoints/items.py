"""
物品模块 API 端点
"""
from typing import Any

from fastapi import APIRouter, HTTPException, status

router = APIRouter()


@router.get("/", response_model=list[dict[str, Any]])
async def list_items():
    """获取物品列表"""
    # TODO: 调用 service 层获取物品列表
    return []


@router.get("/{item_id}", response_model=dict[str, Any])
async def get_item(item_id: int):
    """获取指定物品信息"""
    # TODO: 调用 service 层获取物品详情
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Item {item_id} not found",
    )


@router.post("/", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_item(item_data: dict[str, Any]):
    """创建新物品"""
    # TODO: 调用 service 层创建物品
    return {"id": 1, **item_data}


@router.put("/{item_id}", response_model=dict[str, Any])
async def update_item(item_id: int, item_data: dict[str, Any]):
    """更新物品信息"""
    # TODO: 调用 service 层更新物品
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Item {item_id} not found",
    )


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(item_id: int):
    """删除物品"""
    # TODO: 调用 service 层删除物品
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Item {item_id} not found",
    )
