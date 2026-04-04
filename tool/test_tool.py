from base.types import tool


@tool
def get_weather(city: str) -> str:
    """获取一个城市的天气

    Args:
        city: 城市名称，例如北京、上海
    """
    return f"{city}的天气是晴天"


@tool(name="get_temperature", description="获取指定城市的温度")
def get_temperature(city: str, unit: str = "celsius") -> str:
    """获取指定城市的温度

    Args:
        city: 城市名称
        unit: 温度单位，支持 celsius 或 fahrenheit
    """
    return f"{city}的温度: 25°{unit}"
