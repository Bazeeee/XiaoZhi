#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小智AI美食推荐官 - 完整版
功能：
1. 记忆用户口味偏好、饮食禁忌、消费预算
2. 智能推荐适配菜品
3. 生成美食推荐文案
4. 搜索美食图片
"""

import json
import asyncio
import websockets
import requests
import logging
import os
import random
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==================== 配置区域 ====================
MCP_ENDPOINT = "wss://api.xiaozhi.me/mcp/?token=eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOjkyODUwNiwiYWdlbnRJZCI6MTgxNzA3OSwiZW5kcG9pbnRJZCI6ImFnZW50XzE4MTcwNzkiLCJwdXJwb3NlIjoibWNwLWVuZHBvaW50IiwiaWF0IjoxNzgxMzQ5OTgwLCJleHAiOjE4MTI5MDc1ODB9.jJYbsZwBnx3bq0mE8gZLd2m-LRfHWO_S_TBOLHcK0OHnBYwOe46gJfaPNUaPgkPR7dOMVpx_l9lJe6xQ6vsMPA"

# 智谱AI配置（用于生成推荐文案）
ZHIPU_API_KEY = "fe0654a76d614558a1b76d83bef6895e.eKN0c1swTvZngbG2"
ZHIPU_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

# 图片搜索配置（使用Pexels免费API）
PEXELS_API_KEY = "你的Pexels API Key"  # 从 https://www.pexels.com/api/ 免费获取
PEXELS_API_URL = "https://api.pexels.com/v1/search"

# 数据文件路径
DATA_DIR = Path(__file__).parent / "data"
MEMORY_DIR = Path(__file__).parent / "memory"
RECIPES_FILE = DATA_DIR / "recipes.json"

# 确保目录存在
MEMORY_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# ==================== 菜品数据加载 ====================
def load_recipes():
    """加载菜品数据库"""
    if RECIPES_FILE.exists():
        with open(RECIPES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)['recipes']
    return []

RECIPES = load_recipes()

# ==================== 用户记忆管理 ====================
def get_user_memory(user_id: str) -> dict:
    """获取用户记忆数据"""
    memory_file = MEMORY_DIR / f"{user_id}.json"
    
    if memory_file.exists():
        with open(memory_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    # 默认记忆模板
    return {
        "user_id": user_id,
        "preferences": {
            "cuisine": [],      # 喜欢的菜系
            "flavors": [],      # 喜欢的口味
            "dislikes": [],     # 不喜欢的食材
            "allergies": []     # 过敏食材
        },
        "budget": {
            "per_person": 50,   # 人均预算
            "meal_type": "lunch"
        },
        "history": [],          # 推荐历史
        "last_interaction": None,
        "total_recommendations": 0
    }

def save_user_memory(user_id: str, memory: dict):
    """保存用户记忆"""
    memory["last_interaction"] = datetime.now().isoformat()
    memory_file = MEMORY_DIR / f"{user_id}.json"
    with open(memory_file, 'w', encoding='utf-8') as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)

def update_user_preferences(user_id: str, message: str):
    """根据对话内容智能更新用户偏好"""
    memory = get_user_memory(user_id)
    message_lower = message.lower()
    
    # 口味偏好检测
    flavor_keywords = {
        "麻辣": "麻辣", "辣": "麻辣", "辛辣": "麻辣",
        "酸甜": "酸甜", "糖醋": "酸甜",
        "清淡": "清淡", "清蒸": "清淡",
        "咸香": "咸香", "红烧": "咸香",
        "鲜甜": "鲜甜", "日料": "鲜甜"
    }
    
    for keyword, flavor in flavor_keywords.items():
        if keyword in message_lower and flavor not in memory["preferences"]["flavors"]:
            memory["preferences"]["flavors"].append(flavor)
            logger.info(f"检测到口味偏好: {flavor}")
    
    # 菜系偏好检测
    cuisine_keywords = {
        "川菜": "川菜", "四川": "川菜", "麻辣": "川菜",
        "日料": "日料", "日本": "日料", "寿司": "日料",
        "粤菜": "粤菜", "广东": "粤菜", "早茶": "粤菜",
        "京菜": "京菜", "北京": "京菜"
    }
    
    for keyword, cuisine in cuisine_keywords.items():
        if keyword in message_lower and cuisine not in memory["preferences"]["cuisine"]:
            memory["preferences"]["cuisine"].append(cuisine)
            logger.info(f"检测到菜系偏好: {cuisine}")
    
    # 禁忌检测
    dislike_keywords = ["不要", "不吃", "忌口", "讨厌", "不喜欢"]
    for kw in dislike_keywords:
        if kw in message_lower:
            # 简单提取禁忌词
            if "香菜" in message_lower and "香菜" not in memory["preferences"]["dislikes"]:
                memory["preferences"]["dislikes"].append("香菜")
            if "肥肉" in message_lower and "肥肉" not in memory["preferences"]["dislikes"]:
                memory["preferences"]["dislikes"].append("肥肉")
            if "海鲜" in message_lower and "海鲜" not in memory["preferences"]["dislikes"]:
                memory["preferences"]["dislikes"].append("海鲜")
    
    # 预算检测
    if "预算" in message_lower or "人均" in message_lower:
        import re
        numbers = re.findall(r'(\d+)', message_lower)
        if numbers:
            new_budget = int(numbers[0])
            if new_budget != memory["budget"]["per_person"]:
                memory["budget"]["per_person"] = new_budget
                logger.info(f"更新预算: {new_budget}")
    
    save_user_memory(user_id, memory)
    return memory

def add_to_history(user_id: str, dish_name: str, restaurant: str = "", rating: int = None):
    """添加推荐记录到历史"""
    memory = get_user_memory(user_id)
    memory["history"].append({
        "date": datetime.now().isoformat(),
        "dish": dish_name,
        "restaurant": restaurant,
        "rating": rating
    })
    # 只保留最近20条记录
    if len(memory["history"]) > 20:
        memory["history"] = memory["history"][-20:]
    memory["total_recommendations"] += 1
    save_user_memory(user_id, memory)

# ==================== 菜品推荐引擎 ====================
def recommend_dish(user_id: str) -> dict:
    """根据用户记忆推荐菜品"""
    memory = get_user_memory(user_id)
    preferences = memory["preferences"]
    budget = memory["budget"]["per_person"]
    history_dishes = [h["dish"] for h in memory["history"][-5:]]  # 最近5条
    
    # 计算每个菜品的匹配分数
    scored_recipes = []
    
    for recipe in RECIPES:
        score = 0
        
        # 跳过最近推荐过的
        if recipe["name"] in history_dishes:
            continue
        
        # 跳过超出预算的
        if recipe["price"] > budget:
            continue
        
        # 口味匹配加分
        for flavor in preferences["flavors"]:
            if flavor in recipe["flavors"]:
                score += 3
        
        # 菜系匹配加分
        for cuisine in preferences["cuisine"]:
            if cuisine == recipe["cuisine"]:
                score += 2
        
        # 禁忌减分
        for dislike in preferences["dislikes"]:
            if dislike in recipe["ingredients"] or dislike in recipe["name"]:
                score -= 10  # 强烈减分
        
        # 随机浮动 (±2)
        score += random.uniform(-2, 2)
        
        if score > 0 or len(scored_recipes) < 5:
            scored_recipes.append((score, recipe))
    
    # 按分数排序
    scored_recipes.sort(key=lambda x: x[0], reverse=True)
    
    if scored_recipes:
        return scored_recipes[0][1]
    
    # 如果没有匹配的，返回任意一个在预算内的
    for recipe in RECIPES:
        if recipe["price"] <= budget:
            return recipe
    
    return RECIPES[0] if RECIPES else None

# ==================== 文案生成（智谱AI）====================
async def generate_recommendation_text(user_id: str, dish: dict) -> str:
    """生成个性化的美食推荐文案"""
    memory = get_user_memory(user_id)
    
    # 构建Prompt
    prompt = f"""你是一个温柔、专业的美食推荐官。根据以下信息生成一段推荐文案（30-50字）：

用户口味偏好：{memory['preferences']['flavors']}
用户禁忌：{memory['preferences']['dislikes']}
预算：{memory['budget']['per_person']}元

推荐菜品：{dish['name']}（{dish['cuisine']}）
价格：{dish['price']}元
口味特点：{', '.join(dish['flavors'])}
推荐理由：这道菜符合用户的口味偏好，价格在预算内。

要求：语气亲切自然，先描述菜品诱人的味道，再提醒价格合适，最后询问是否想尝试。不要使用markdown。"""
    
    if not ZHIPU_API_KEY or "你的" in ZHIPU_API_KEY:
        # 无API Key时的默认文案
        return f"推荐您试试{dish['name']}，{'、'.join(dish['flavors'])}风味，人均{dish['price']}元，价格合适，想尝一口吗？"
    
    try:
        headers = {
            "Authorization": f"Bearer {ZHIPU_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "glm-4-flash",
            "messages": [
                {"role": "system", "content": "你是专业的美食推荐官，生成简短亲切的推荐语。"},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 150,
            "temperature": 0.7
        }
        
        response = requests.post(ZHIPU_API_URL, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", f"推荐您试试{dish['name']}！")
        else:
            return f"推荐您试试{dish['name']}，{'、'.join(dish['flavors'])}风味，人均{dish['price']}元~"
            
    except Exception as e:
        logger.error(f"文案生成失败: {e}")
        return f"推荐您试试{dish['name']}，{'、'.join(dish['flavors'])}风味，只要{dish['price']}元！"

# ==================== 图片搜索 ====================
async def search_food_image(dish_name: str) -> dict:
    """搜索菜品图片"""
    if not PEXELS_API_KEY or "你的" in PEXELS_API_KEY:
        # 无API Key时返回默认图片
        return {
            "success": True,
            "image_url": "https://images.pexels.com/photos/1640777/pexels-photo-1640777.jpeg",
            "message": f"为您找到{dish_name}的参考图片"
        }
    
    try:
        headers = {"Authorization": PEXELS_API_KEY}
        params = {
            "query": f"food {dish_name}",
            "per_page": 5,
            "page": 1
        }
        
        response = requests.get(PEXELS_API_URL, headers=headers, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            photos = data.get("photos", [])
            
            if photos:
                selected = random.choice(photos)
                image_url = selected.get("src", {}).get("large", "")
                return {
                    "success": True,
                    "image_url": image_url,
                    "message": f"为您找到{dish_name}的美食图片"
                }
        
        return {
            "success": True,
            "image_url": "https://images.pexels.com/photos/1640777/pexels-photo-1640777.jpeg",
            "message": f"这是{dish_name}的参考图片"
        }
        
    except Exception as e:
        logger.error(f"图片搜索失败: {e}")
        return {
            "success": True,
            "image_url": "https://images.pexels.com/photos/1640777/pexels-photo-1640777.jpeg",
            "message": f"为您找到{dish_name}的参考图片"
        }

# ==================== 主推荐流程 ====================
async def handle_recommendation(user_id: str, message: str = "") -> dict:
    """完整的推荐流程"""
    # 1. 更新用户记忆（从对话中学习）
    update_user_preferences(user_id, message)
    
    # 2. 推荐菜品
    dish = recommend_dish(user_id)
    if not dish:
        return {
            "success": False,
            "message": "抱歉，暂时没有找到合适的推荐",
            "image_url": None
        }
    
    # 3. 生成推荐文案
    text = await generate_recommendation_text(user_id, dish)
    
    # 4. 搜索图片
    image_result = await search_food_image(dish["name"])
    
    # 5. 记录推荐历史
    add_to_history(user_id, dish["name"])
    
    return {
        "success": True,
        "dish": dish["name"],
        "price": dish["price"],
        "flavors": dish["flavors"],
        "message": text,
        "image_url": image_result.get("image_url"),
        "history_count": get_user_memory(user_id)["total_recommendations"]
    }

# ==================== MCP消息处理 ====================
async def handle_mcp_message(websocket, message):
    try:
        data = json.loads(message)
        method = data.get("method")
        msg_id = data.get("id")
        
        logger.info(f"📨 收到: {method} id={msg_id}")
        
        # 初始化
        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {"listChanged": True}},
                    "serverInfo": {"name": "food-recommender", "version": "2.0.0"}
                }
            }
            await websocket.send(json.dumps(response))
            logger.info("✅ 初始化完成")
        
        # 返回工具列表
        elif method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "tools": [
                        {
                            "name": "recommend_food",
                            "description": "根据用户口味偏好推荐美食，返回菜品名称、推荐文案和图片",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "user_id": {
                                        "type": "string",
                                        "description": "用户标识，用于记忆个性化偏好"
                                    },
                                    "message": {
                                        "type": "string",
                                        "description": "用户的额外需求或偏好描述"
                                    }
                                },
                                "required": ["user_id"]
                            }
                        },
                        {
                            "name": "update_preference",
                            "description": "更新用户的口味偏好或禁忌",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "user_id": {"type": "string"},
                                    "preference_type": {"type": "string", "enum": ["flavor", "cuisine", "dislike", "budget"]},
                                    "value": {"type": "string"}
                                },
                                "required": ["user_id", "preference_type", "value"]
                            }
                        }
                    ]
                }
            }
            await websocket.send(json.dumps(response))
            logger.info("✅ 工具列表已返回")
        
        # 工具调用
        elif method == "tools/call":
            tool_name = data.get("params", {}).get("name")
            arguments = data.get("params", {}).get("arguments", {})
            
            if tool_name == "recommend_food":
                user_id = arguments.get("user_id", "default_user")
                message = arguments.get("message", "")
                
                logger.info(f"🍽️ 为用户 {user_id[:8]} 推荐美食")
                
                result = await handle_recommendation(user_id, message)
                
                response_text = f"{result['message']}\n图片：{result.get('image_url', '')}"
                
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [{"type": "text", "text": response_text}]
                    }
                }
                await websocket.send(json.dumps(response))
                logger.info(f"✅ 推荐完成: {result.get('dish')}")
            
            elif tool_name == "update_preference":
                user_id = arguments.get("user_id", "default_user")
                pref_type = arguments.get("preference_type")
                value = arguments.get("value")
                
                memory = get_user_memory(user_id)
                
                if pref_type == "flavor":
                    if value not in memory["preferences"]["flavors"]:
                        memory["preferences"]["flavors"].append(value)
                elif pref_type == "cuisine":
                    if value not in memory["preferences"]["cuisine"]:
                        memory["preferences"]["cuisine"].append(value)
                elif pref_type == "dislike":
                    if value not in memory["preferences"]["dislikes"]:
                        memory["preferences"]["dislikes"].append(value)
                elif pref_type == "budget":
                    memory["budget"]["per_person"] = int(value)
                
                save_user_memory(user_id, memory)
                
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [{"type": "text", "text": f"已更新您的{pref_type}偏好：{value}"}]
                    }
                }
                await websocket.send(json.dumps(response))
                logger.info(f"✅ 偏好已更新")
        
        # 心跳
        elif method == "ping":
            response = {"jsonrpc": "2.0", "id": msg_id, "result": {}}
            await websocket.send(json.dumps(response))
        
        elif method == "notifications/initialized":
            logger.info("✅ 客户端已就绪")
            
    except Exception as e:
        logger.error(f"❌ 处理异常: {e}")

# ==================== 主连接 ====================
async def connect_mcp():
    while True:
        try:
            async with websockets.connect(
                MCP_ENDPOINT,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=10
            ) as websocket:
                logger.info("✅ 已连接到小智MCP服务器")
                logger.info("🍽️ 美食推荐官服务已启动")
                
                async for message in websocket:
                    await handle_mcp_message(websocket, message)
                    
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"⚠️ 连接断开: {e.code}，5秒后重连...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"❌ 连接异常: {e}，10秒后重试...")
            await asyncio.sleep(10)

# ==================== 入口 ====================
if __name__ == "__main__":
    print("=" * 60)
    print("🍽️ 小智AI美食推荐官 - 完整版 v2.0")
    print("功能：记忆偏好 | 智能推荐 | 文案生成 | 图片展示")
    print("=" * 60)
    
    if "你的token" in MCP_ENDPOINT:
        print("❌ 请先配置 MCP_ENDPOINT")
        print("   获取：小智控制台 -> 配置角色 -> MCP设置 -> 获取MCP接入点")
        exit(1)
    
    asyncio.run(connect_mcp())