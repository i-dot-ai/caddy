import pytest
from mcp.types import ListToolsResult

from api.mcp_app import ToolResponse


@pytest.mark.asyncio()
async def test_mcp_tool_call(
    client, fresh_session_manager, collection_manager, example_document
):
    headers = {
        "Accept": "application/json,text/event-stream",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {collection_manager.user.token}",
    }

    tool_call_message = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": collection_manager.collection.slug,
            "arguments": {"query": "hello", "keywords": []},
        },
    }

    async with fresh_session_manager.run():
        response = client.post("/search/mcp/", json=tool_call_message, headers=headers)

    assert response.status_code == 200

    response_json = response.json()
    tool_response = ToolResponse.model_validate_json(
        response_json["result"]["content"][0]["text"]
    )

    actual = tool_response.documents[0].model_dump()
    assert actual["page_content"] == example_document.text
    assert actual["metadata"]["resource_id"] == str(example_document.resource_id)


@pytest.mark.asyncio()
async def test_mcp_tools_list(
    client, fresh_session_manager, collection_manager, another_example_collection
):
    headers = {
        "Accept": "application/json,text/event-stream",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {collection_manager.user.token}",
    }

    tool_call_message = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
    }

    async with fresh_session_manager.run():
        response = client.post("/search/mcp/", json=tool_call_message, headers=headers)

    assert response.status_code == 200

    tool_response = ListToolsResult.model_validate(response.json()["result"])
    available_tools = [tool.name for tool in tool_response.tools]

    # collection_manager connects the associated user with an associated collection
    assert collection_manager.collection.name in available_tools
    # but not to some other unrelated collection
    assert another_example_collection.name not in available_tools


@pytest.mark.asyncio()
async def test_mcp_tools_list_none(
    client,
    fresh_session_manager,
    example_collection,
    normal_user,
):
    headers = {
        "Accept": "application/json,text/event-stream",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {normal_user.token}",
    }

    tool_call_message = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
    }

    async with fresh_session_manager.run():
        response = client.post("/search/mcp/", json=tool_call_message, headers=headers)

    assert response.status_code == 200

    tool_response = ListToolsResult.model_validate(response.json()["result"])
    assert not tool_response.tools
