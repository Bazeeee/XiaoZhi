from mcp.server.fastmcp import FastMCP
import requests
import os

mcp = FastMCP("XiaoZhi Image Gen")

@mcp.tool()
def generate_image(prompt: str) -> dict:
    """根据文字描述生成图片"""
    print(f"📝 收到绘图指令: {prompt}")
    # 这里替换为你真实的绘图 API 调用逻辑，如 DALL-E 3
    api_key = os.environ.get("IMAGE_API_KEY")
    response = requests.post('YOUR_IMAGE_API_URL', json={
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024"
    }, headers={"Authorization": f"Bearer {api_key}"})
    data = response.json()
    image_url = data['data'][0]['url']
    # 返回结果给音箱
    return {"success": True, "image_url": image_url, "message": f"已生成图片：{prompt}"}

if __name__ == "__main__":
    mcp.run(transport="stdio")