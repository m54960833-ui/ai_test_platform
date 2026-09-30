# AITestPlatform・AI 辅助接口自动化测试平台

一个 "接口自动化测试 + AI 大模型辅助" 的轻量平台：内置一个电商 Demo 被测服务

（认证 / 用户 / 订单），用**数据驱动**的方式管理接口测试用例，可一键执行并产出

HTML 测试报告；同时接入大模型自动生成测试用例、对失败用例做 Badcase 归因分析，

并带一个 Web 可视化管理界面。

没有配置大模型 Key 时，会自动降级为**模板生成**，整条链路（生成→执行→报告→分析）

照样能跑通演示，适合没 Key 也能自测。

## 技术栈



* 被测服务 / Web 平台：**FastAPI + uvicorn**，SQLite（标准库 sqlite3）存储

* 测试执行：**requests + 自研数据驱动 runner**（YAML 用例）

* AI 引擎：OpenAI 兼容接口（默认对接**智谱 GLM**，兼容火山方舟 / 豆包等），无 Key 时模板兜底

* 报告：JSON + 原生 HTML（Jinja2 渲染）

* 前端：原生 HTML/CSS/JS，无框架

## 目录结构



```
ai\_test\_platform/

├── run.py               # 统一入口：server / test / web / dev

├── config.yaml          # 全局配置（端口、超时、AI 参数）

├── requirements.txt

├── app/                 # 内置 Demo 被测服务（电商用户/订单/认证）

│   └── routers/         #   auth / users / orders 接口

├── core/                # 测试平台核心

│   ├── case\_loader.py   #   用例加载（YAML/JSON → Case）

│   ├── runner.py        #   执行引擎：变量串联、断言、保存

│   ├── http\_client.py   #   HTTP 封装：登录态、超时、重试

│   ├── reporter.py      #   报告生成（JSON + HTML）

│   ├── llm\_engine.py    #   AI 生成用例 / Badcase 分析 + 模板兜底

│   └── utils.py         #   配置读取、极简 jsonpath 等

├── cases/               # 数据驱动用例（YAML）

│   └── \_ai\_generated/   #   AI 批量生成的用例（需人工精修后纳入回归）

├── web/                 # Web 可视化管理平台

│   └── static/          #   仪表盘前端

├── data/                # SQLite 库（首次启动服务自动生成）

└── reports/             # 测试报告输出
```

## 快速开始



```
pip install -r requirements.txt

\# 方式一：只跑命令行测试（会自动等被测服务在线）

python run.py server      # 终端1：启动被测服务(8001)

python run.py test        # 终端2：跑全部用例，生成报告

\# 方式二：直接开 Web 管理平台（一条命令同时起被测服务）

python run.py web         # 打开 http://127.0.0.1:8002
```

`run.py test` 默认对内置 23 条精选用例执行，结果 100% 通过，报告在

`reports/report_*.html`，浏览器直接打开即可。

## 核心特性



1. **数据驱动用例**：用例用 YAML 声明，支持

   `@{envKey}` 变量引用、`@rand` 随机后缀、`save` 跨用例传参（注册→登录→鉴权调用）

2. **断言类型**：`status_code` / `jsonpath` / `contains` / `regex`，覆盖正常 + 异常 + 参数校验场景

3. **执行引擎**：一次执行维护全局 env，自动处理登录态（先 login 再调业务接口）

4. **报告**：JSON + HTML 双份，记录每个用例的状态码、耗时、失败断言与原始响应

5. **AI 生成用例**：读取被测服务 `/openapi.json`，让大模型批量产出测试用例

6. **AI Badcase 分析**：对失败用例做归因（无 Key 时走本地规则粗粒度归因）

7. **Web 平台**：查看用例、一键执行、历史报告、AI 生成 / 分析

## 接入真实大模型（可选）

默认已对接**智谱 GLM**（`glm-4-flash`）。API Key 放在项目根目录的 `.env` 文件里

（该文件已被 `.gitignore` 忽略，不会进仓库）：



```
\# .env

ZHIPU\_API\_KEY=你的智谱Key
```

配置好后重启 Web，AI 生成 / 分析即切换到真实大模型；也可用环境变量临时生效：

`$env:ZHIPU_API_KEY = "你的 Key"`。

`config.yaml` 的 `llm` 段默认指向智谱 OpenAI 兼容接口，想换平台（如火山方舟豆包）

改 `llm.base_url` 和 `llm.model` 即可。未配置 Key 时自动降级为模板生成，功能不缺失。

## 说明



* 被测服务是演示用 Demo，接口 / 数据库仅供平台自测；接入真实被测对象时改 `config.yaml`

  里的 server 地址即可

* AI 生成的用例是 "初稿"，建议人工复核参数和断言后再纳入回归，这也符合

  "AI 提效 + 人工质量把关" 的测试工作流