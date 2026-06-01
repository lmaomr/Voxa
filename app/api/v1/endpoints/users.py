"""
用户模块 API 端点
"""
from typing import Any

from fastapi import APIRouter, HTTPException, status

router = APIRouter()


@router.get("/", response_model=list[dict[str, Any]])
async def list_users():
    """获取用户列表"""
    # TODO: 调用 service 层获取用户列表
    return []


@router.get("/{user_id}", response_model=dict[str, Any])
async def get_user(user_id: int):
    """获取指定用户信息"""
    # TODO: 调用 service 层获取用户详情
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"User {user_id} not found",
    )


@router.post("/", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_user(user_data: dict[str, Any]):
    """创建新用户"""
    # TODO: 调用 service 层创建用户
    return {"id": 1, **user_data}


@router.put("/{user_id}", response_model=dict[str, Any])
async def update_user(user_id: int, user_data: dict[str, Any]):
    """更新用户信息"""
    # TODO: 调用 service 层更新用户
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"User {user_id} not found",
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int):
    """删除用户"""
    # TODO: 调用 service 层删除用户
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"User {user_id} not found",
    )
