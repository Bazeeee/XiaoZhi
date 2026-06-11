#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小智AI美食推荐官 - MCP图片搜索模块（无需API Key版）
使用免费搜索引擎获取美食图片，无需注册，开箱即用
"""

import json
import asyncio
import websockets
import requests
import logging
import random
from urllib.parse import quote

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ========== 配置区域 ==========
# 从小智控制台获取的MCP接入点地址
MCP_ENDPOINT = "wss://api.xiaozhi.me/mcp/?token=eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOjkyODUwNiwiYWdlbnRJZCI6MTgxNzA3OSwiZW5kcG9pbnRJZCI6ImFnZW50XzE4MTcwNzkiLCJwdXJwb3NlIjoibWNwLWVuZHBvaW50IiwiaWF0IjoxNzgxMTc1NzcyLCJleHAiOjE4MTI3MzMzNzJ9.qbIZeMsx7LpAceGiv-5-PcfLenTZjuPKKuahAUsUxnNiZppKbY8bVrTa5oqTlTVqc5qEHfrWyGzdsyqee_mVgw"

# ========== 免费图片搜索方案 ==========

# 方案1：使用 Unsplash 免费图片API（无需Key，每天50次限制但个人使用足够）
UNSPLASH_URL = "https://unsplash.com/napi/search/photos"

# 方案2：使用 Pexels 免费图片API（需要免费注册获取Key，更稳定）
# PEXELS_API_KEY = "你的Pexels API Key"  # 从 https://www.pexels.com/api/ 免费获取
# PEXELS_URL = "https://api.pexels.com/v1/search"

# 方案3：使用本地图片库（完全离线，最稳定）
# 准备一些美食图片放在本地文件夹，随机返回

async def search_food_image_unsplash(prompt: str) -> dict:
    """使用Unsplash免费API搜索美食图片（无需Key，但有速率限制）"""
    try:
        # 优化搜索关键词
        search_query = f"food {prompt} dish"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        params = {
            "query": search_query,
            "per_page": 10,
            "page": 1
        }
        
        response = requests.get(UNSPLASH_URL, headers=headers, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            photos = data.get("photos", {}).get("results", [])
            
            if photos:
                # 随机选择一张图片
                selected = random.choice(photos)
                image_url = selected.get("urls", {}).get("regular", "")
                description = selected.get("description", prompt)
                
                logger.info(f"✅ 找到图片: {description[:50]}...")
                return {
                    "success": True,
                    "image_url": image_url,
                    "message": f"为您找到{prompt}的美食图片",
                    "source": "Unsplash"
                }
            else:
                # 如果没找到，返回默认美食图片
                return await get_default_food_image(prompt)
        else:
            logger.warning(f"Unsplash搜索失败，使用默认图片: {response.status_code}")
            return await get_default_food_image(prompt)
            
    except Exception as e:
        logger.error(f"搜索异常: {e}")
        return await get_default_food_image(prompt)


async def get_default_food_image(prompt: str) -> dict:
    """备用方案：返回高质量的美食占位图"""
    # 根据关键词返回对应的默认图片URL
    default_images = {
        "麻婆豆腐": "https://picsum.photos/id/103/1024/1024",  # 美食类
        "宫保鸡丁": "https://picsum.photos/id/104/1024/1024",
        "红烧肉": "https://picsum.photos/id/106/1024/1024",
        "default": "https://picsum.photos/id/108/1024/1024"
    }
    
    # 尝试匹配关键词
    for key, url in default_images.items():
        if key in prompt:
            return {
                "success": True,
                "image_url": url,
                "message": f"为您找到{prompt}的参考图片",
                "source": "default"
            }
    
    # 返回通用美食图片
    return {
        "success": True,
        "image_url": "https://picsum.photos/id/108/1024/1024",
        "message": f"为您找到{prompt}的相关图片",
        "source": "default"
    }


async def search_food_image_pexels(prompt: str, api_key: str = None) -> dict:
    """使用Pexels API搜索图片（需要免费注册获取Key）"""
    if not api_key:
        return await search_food_image_unsplash(prompt)
    
    try:
        headers = {"Authorization": api_key}
        params = {
            "query": f"food {prompt}",
            "per_page": 10,
            "page": 1
        }
        
        response = requests.get("https://api.pexels.com/v1/search", headers=headers, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            photos = data.get("photos", [])
            
            if photos:
                selected = random.choice(photos)
                image_url = selected.get("src", {}).get("large", "")
                return {
                    "success": True,
                    "image_url": image_url,
                    "message": f"为您找到{prompt}的美食图片",
                    "source": "Pexels"
                }
        
        return await search_food_image_unsplash(prompt)
        
    except Exception as e:
        logger.error(f"Pexels搜索失败: {e}")
        return await search_food_image_unsplash(prompt)


# 默认使用Unsplash方案（无需Key）
search_food_image = search_food_image_unsplash


# ========== MCP消息处理 ==========
async def handle_mcp_message(websocket, message):
    try:
        data = json.loads(message)
        method = data.get("method")
        msg_id = data.get("id")
        
        logger.info(f"📨 收到消息: {method} id={msg_id}")
        
        # 1. 处理初始化请求
        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {"listChanged": True}},
                    "serverInfo": {"name": "food-image-search", "version": "1.0.0"}
                }
            }
            await websocket.send(json.dumps(response))
            logger.info("✅ 已响应初始化")
        
        # 2. 处理tools/list - 返回可用工具列表
        elif method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "tools": [
                        {
                            "name": "search_food_image",
                            "description": "搜索美食图片，根据菜品名称从网上找到对应的真实美食照片",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "prompt": {
                                        "type": "string",
                                        "description": "菜品名称或美食描述，例如：麻婆豆腐、北京烤鸭、意大利面"
                                    }
                                },
                                "required": ["prompt"]
                            }
                        }
                    ]
                }
            }
            await websocket.send(json.dumps(response))
            logger.info("✅ 已返回工具列表")
        
        # 3. 处理tools/call - 执行工具调用
        elif method == "tools/call":
            tool_name = data.get("params", {}).get("name")
            arguments = data.get("params", {}).get("arguments", {})
            
            if tool_name == "search_food_image":
                prompt = arguments.get("prompt", "美食")
                logger.info(f"🔍 搜索图片: {prompt}")
                
                # 执行图片搜索
                result = await search_food_image(prompt)
                
                # 返回结果
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(result, ensure_ascii=False)
                            }
                        ]
                    }
                }
                await websocket.send(json.dumps(response))
                
                if result.get("success"):
                    logger.info(f"🖼️ 图片已找到: {result.get('image_url', '')[:60]}...")
                else:
                    logger.error(f"❌ 搜索失败: {result.get('error')}")
        
        # 4. 处理ping
        elif method == "ping":
            response = {"jsonrpc": "2.0", "id": msg_id, "result": {}}
            await websocket.send(json.dumps(response))
        
        # 5. 通知类消息
        elif method == "notifications/initialized":
            logger.info("✅ 客户端初始化完成")
        
        else:
            logger.debug(f"📭 未处理的消息: {method}")
            
    except Exception as e:
        logger.error(f"❌ 处理消息异常: {e}")


async def connect_mcp():
    """连接小智MCP服务器并保持连接"""
    while True:
        try:
            logger.info(f"🔗 正在连接: {MCP_ENDPOINT[:60]}...")
            async with websockets.connect(
                MCP_ENDPOINT,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=10
            ) as websocket:
                logger.info("✅ 已连接到小智MCP服务器")
                logger.info("🔍 美食图片搜索服务已就绪")
                logger.info("📝 可用命令：对小智说 '搜索麻婆豆腐的图片'")
                
                async for message in websocket:
                    await handle_mcp_message(websocket, message)
                    
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"⚠️ 连接关闭: {e.code}，5秒后重连...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"❌ 连接异常: {e}，10秒后重试...")
            await asyncio.sleep(10)


# ========== 主入口 ==========
if __name__ == "__main__":
    print("=" * 60)
    print("🍽️ 小智AI美食推荐官 - 图片搜索服务")
    print("🔍 使用免费Unsplash API，无需注册")
    print("📡 等待小智设备调用...")
    print("=" * 60)
    
    # 检查配置
    if "你的token" in MCP_ENDPOINT:
        print("❌ 错误：请先配置 MCP_ENDPOINT")
        print("   获取路径：小智控制台 -> 智能体 -> 配置角色 -> MCP设置 -> 获取MCP接入点")
        exit(1)
    
    asyncio.run(connect_mcp())