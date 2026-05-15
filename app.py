import eventlet
eventlet.monkey_patch()

from flask import Flask, send_from_directory, jsonify
from flask_socketio import SocketIO, emit
from openai import OpenAI
from bs4 import BeautifulSoup as bs
import os
import requests

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("openrouterkey")
)

app = Flask(__name__, static_folder="web")
socketio = SocketIO(app, async_mode="eventlet")

chats = {}

tool_registry = {}
tool_registry2 = []

def tool(func_or_name=None):
    def decorator(func):
        name = func_or_name if isinstance(func_or_name, str) else func.__name__
        tool_registry[name] = func
        tool_registry2.append(func)
        return func

    if callable(func_or_name):
        return decorator(func_or_name)

    return decorator

def get_tools_schema(tools_list):
    schema = []
    for t in tools_list:
        if callable(t):
            import inspect
            sig = inspect.signature(t)
            params = {k: {"type": "string"} for k in sig.parameters}
            schema.append({
                "type": "function",
                "function": {
                    "name": t.__name__,
                    "description": t.__doc__ or "",
                    "parameters": {"type": "object", "properties": params, "required": list(params.keys())}
                }
            })
        else:
            schema.append(t)
    return schema

def fetch(url):
    try:
        return requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"}).text
    except:
        return "<h1>NXDOMAIN</h1><p>NXDOMAIN: The requested webserver couldn't be contacted or doesn't exist. Try using web search?</p>"

@tool
def web_search(query: str):
    s = bs(fetch(f"https://startpage.com/search?q={query}"), features="html.parser")
    rtext = ""

    for result in s.find_all(class_="result")[:5]:
        try:
            rtext = f"{rtext}{result.find("a", class_="result-title").find("h2").text}\n{result.find("p", class_="description").text}\n{result.find("a", class_="result-title")["href"]}\n\n"
        except:
            continue

    return rtext.strip()

@tool
def view_webpage(url: str):
    try:
        s = bs(fetch(url), features="html.parser")
        for i in s(["script", "style", "meta", "img", "input", "textarea"]):
            i.decompose()
        return s.get_text(separator="\n", strip=True)[:1000]
    except:
        return "<h1>422</h1>\n<p>error 422: Try again later. Move on to a different page.</p>"

@app.route("/")
def home():
    return send_from_directory(app.static_folder, "index.html")

@socketio.on("user")
def user(data):
    prompt = data["content"]
    id = data["id"]
    model = "openai/gpt-oss-120b:free" if data["model"] == "smart" else "nvidia/nemotron-3-nano-30b-a3b:free"

    if not id in chats:
        chats[id] = [{"role": "system", "content": "You are a helpful AI assistant named Vortex.\nVortex should search the web for information if it does not have information about the subject"}]
    messages = chats[id]
    messages.append({"role": "user", "content": prompt})

    emit("assistant_newl", "")
    
    finished = False
    while finished == False:
        hasContent = False
        thought = False
        ou = ""
        toolCalls = []
        stream = client.chat.completions.create(model=model, messages=messages, tools=get_tools_schema(tool_registry2), reasoning_effort="medium", stream=True)
        for chunk in stream:
            delta = chunk.choices[0].delta

            if delta.content:
                if not hasContent:
                    emit("indicate", "")
                hasContent = True
                ou += delta.content
                emit("assistant", delta.content)

            if delta.tool_calls:
                for tcchunk in delta.tool_calls:
                    if len(toolCalls) <= tcchunk.index:
                        toolCalls.append(tcchunk)
                    else:
                        if tcchunk.function.arguments:
                            toolCalls[tcchunk.index].function.arguments += tcchunk.function.arguments
        
        if toolCalls:
            messages.append({"role": "assistant", "content": ou, "tool_calls": toolCalls})
            for toolcall in toolCalls:
                if toolcall.function.name in tool_registry:
                    emit("indicate", f"Using {str(toolcall.function.name).replace('_', ' ')}...")
                    import json
                    args = json.loads(toolcall.function.arguments)
                    result = tool_registry[toolcall.function.name](**args)
                    messages.append({"role": "tool", "tool_call_id": toolcall.id, "content": str(result)})
            ou = ""
        else:
            messages.append({"role": "assistant", "content": ou})

        if ou != "":
            finished = ou
    
    emit("finw", "")


@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

if __name__ == "__main__":
    socketio.run(app)
