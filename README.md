# Chronicle of Scarlet 存档工具

这是一个面向 `Chronicle of Scarlet` 的本地存档解密、回写和简易编辑工具。

当前仓库同时提供两种使用方式：

- 浏览器版：打开单文件 HTML 页面，上传 `.save` 后直接修改并下载新存档。
- Python 脚本版：在 `.save` 和 `.json` 之间互相转换。

当前工作区只保留了最终可用的核心文件：

- `save-editor.html`：单文件浏览器版存档编辑器。
- `main.py`：存档解密与回写脚本。
- `motaSave21.save`：示例存档。
- `motaSave21.json`：示例存档对应的 JSON。

## 功能说明

浏览器版支持：

- 上传 `.save` 文件后自动解密。
- 在页面里修改一组固定基础数值。
- 点击下载后自动重新封装为可读取的 `.save` 文件。

Python 脚本版支持两种方向的转换：

- `.save -> .json`：把游戏存档解密并导出为可编辑 JSON。
- `.json -> .save`：把修改后的 JSON 重新封装为游戏可读取的存档。

两种方式底层处理的都是同一套 Godot 数据格式：

1. 外层 `GDEC` 加密容器。
2. 内层 `store_var(String)` 写出的 Variant String。

## 存档位置

Windows 默认存档目录：

```text
C:\Users\${YourName}\AppData\Roaming\Godot\app_userdata\Chronicle of Scarlet
```

把 `${YourName}` 替换成你的 Windows 用户名。

## 依赖

浏览器版不需要安装依赖，直接打开 `save-editor.html` 即可。

Python 脚本版只需要安装 Python 和 `pycryptodome`：

```bash
pip install pycryptodome
```

## 用法

### 浏览器版

直接用浏览器打开 `save-editor.html`。

页面流程：

1. 上传 `.save` 文件。
2. 修改页面里的基础数值。
3. 按需使用快捷按钮：
	- `当前 HP/MP 补满`
	- `大法师模式`：把 `mp` 和 `maxMp` 一起改成 `255`
	- `金币改成 999999`
4. 点击“下载修改后的 `.save`”。

### Python 脚本版

脚本只保留两个参数：`-i` 和 `-o`。

#### 解密存档为 JSON

```bash
python .\main.py -i .\motaSave21.save -o .\motaSave21.json
```

#### 将 JSON 回写为存档

```bash
python .\main.py -i .\motaSave21.json -o .\motaSave21.save
```

脚本会根据输入输出扩展名自动判断当前是“解密”还是“回写”：

- `.save -> .json`：自动执行解密。
- `.json -> .save`：自动执行回写。

## 注意事项

- 回写时会自动把 `saveCode` 修正为游戏期望值，避免生成能解密但不能载入的存档。
- 建议在修改前先备份原始 `.save` 文件。
- 如果输入文件不是 `GDEC` 格式，脚本会直接报错。

## 说明

本工具代码与本 README 由 GitHub Copilot 使用 GPT-5.4 生成，并在当前工作区内完成实际验证。