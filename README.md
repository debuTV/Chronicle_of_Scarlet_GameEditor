# Chronicle of Scarlet 存档工具

这是一个面向 `Chronicle of Scarlet` 的本地存档解密/回写工具。

当前工作区只保留了最终可用的核心文件：

- `main.py`：存档解密与回写脚本。
- `motaSave21.save`：示例存档。
- `motaSave21.json`：示例存档对应的 JSON。

## 功能说明

这个脚本支持两种方向的转换：

- `.save -> .json`：把游戏存档解密并导出为可编辑 JSON。
- `.json -> .save`：把修改后的 JSON 重新封装为游戏可读取的存档。

脚本已经处理了两层 Godot 数据格式：

1. 外层 `GDEC` 加密容器。
2. 内层 `store_var(String)` 写出的 Variant String。

## 依赖

脚本依赖 Python 和 `pycryptodome`。

当前工作区默认使用虚拟环境：

- `.\.venv\Scripts\python.exe`

如果你在别的环境运行，需要先安装：

```bash
pip install pycryptodome
```

## 用法

脚本只保留两个参数：`-i` 和 `-o`。

### 解密存档为 JSON

```bash
python .\main.py -i .\motaSave21.save -o .\motaSave21.json
```

### 将 JSON 回写为存档

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