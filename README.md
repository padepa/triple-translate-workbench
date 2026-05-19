# 多语翻译工作台

一个本地多语言翻译/回译工作台。当前版本内置一条中文回译链路：

```text
中文 -> 英文 -> 日文 -> 中文
```

它可以用来观察文本在多轮翻译后的表达变化。结果可能改变原意，请在正式使用前人工核对事实、语气和关键表述。

后续可以扩展为自定义语言链路，例如中文、英文、日文、韩文、法文等不同组合。

## 功能

- 原生 Windows 桌面窗口，启动轻量，不依赖浏览器内核。
- 支持自动换翻译引擎。
- 支持多引擎对比。
- 支持命令行、剪贴板和图形界面三种使用方式。
- 针对 Windows 150% 等高 DPI 缩放做了清晰度处理。

## 下载 Windows 版

前往 Releases 下载：

https://github.com/padepa/polyglot-translation-workbench/releases/latest

下载 `PolyglotTranslationWorkbench-v0.1.0-windows-x64.zip`，解压后运行：

```text
PolyglotTranslationWorkbench.exe
```

## 安装依赖

需要 Python 3.10+。

```powershell
python -m pip install -r requirements.txt
```

## 图形界面

开发环境直接运行：

```powershell
python .\native_tk_app.py
```

Windows 上也可以双击：

```text
start_workbench.bat
```

如果已经用 PyInstaller 打包，启动脚本会优先打开：

```text
dist\PolyglotTranslationWorkbench\PolyglotTranslationWorkbench.exe
```

否则会回退到 `pythonw native_tk_app.py`。

## 命令行用法

从剪贴板读取文本，显示三步过程，并把最终结果复制回剪贴板：

```powershell
python .\triple_translate.py --show-steps --copy
```

手动传入文本：

```powershell
python .\triple_translate.py --text "这里放你要处理的中文。" --show-steps
```

对比多个翻译引擎：

```powershell
python .\triple_translate.py --compare --show-steps
```

列出当前 `translators` 库支持的引擎：

```powershell
python .\triple_translate.py --list-engines
```

指定引擎：

```powershell
python .\triple_translate.py --engines google,youdao,alibaba --show-steps
```

## 打包 Windows EXE

安装额外构建依赖：

```powershell
python -m pip install pyinstaller
```

打包：

```powershell
pyinstaller --noconfirm .\PolyglotTranslationWorkbench.spec
```

产物位置：

```text
dist\PolyglotTranslationWorkbench\PolyglotTranslationWorkbench.exe
```

## 注意

本项目使用 [`translators`](https://pypi.org/project/translators/) 调用公共翻译服务。公共接口可能受网络、地区、频率限制和服务变更影响。如果需要更稳定的生产级翻译，建议改接官方 API，例如 DeepL、Google Cloud Translation、Microsoft Azure AI Translator、百度翻译开放平台、有道智云等。

## License

MIT
