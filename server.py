import json
import sqlite3
from pathlib import Path

from mcp.server.mcpserver import MCPServer

DB_PATH = Path(__file__).parent / "data" / "demo.db"
CONNECTION = sqlite3.connect(DB_PATH, check_same_thread=False)

server = MCPServer("shebao-server")

@server.tool()
def search_cards(keyword: str) -> str:
    """根据关键词检索公共事务条目，返回匹配条目的 ID 和标题。keyword 为检索关键词，如：工伤"""
    cursor = CONNECTION.cursor()
    cursor.execute("""
        SELECT id, title FROM public_affairs
        WHERE sub_item LIKE ?
        LIMIT 5
    """, (f"%{keyword}%",))
    searchs = cursor.fetchall()
    if not searchs:
        return "未检索到任何数据!"
    result = []
    for card in searchs:
        column = {}
        for key, val in zip(["ID", "标题"], card):
            column[key] = val
        result.append(column)
    return json.dumps(result, ensure_ascii=False)


@server.tool()
def get_card_by_id(row_id: int) -> str:
    """按 ID 查询单条公共事务条目的完整信息。row_id 为条目的数字编号，如：46"""
    cursor = CONNECTION.cursor()
    cursor.execute("""
            SELECT * FROM public_affairs
            WHERE id = ?
        """, (row_id,))
    search = cursor.fetchone()
    if not search:
        return "未检索到任何数据!"
    labels = ['ID', '标题', '主项名称', '子项名称', '法定办结时限', '申请材料清单',
              '申请表单信息项', '办结反馈信息项', '受理条件', '二级子项', '设定依据',
              '办理流程', '服务对象', '行使层级']
    result = {}
    for key, val in zip(labels, search):
        result[key] = val
    return json.dumps(result, ensure_ascii=False)


if __name__ == "__main__":
    server.run("stdio")
