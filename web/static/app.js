// AITestPlatform 前端逻辑，原生 JS，不引框架
const $ = (id) => document.getElementById(id);

async function api(url, opt) {
  const resp = await fetch(url, opt);
  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new Error(text || `请求失败(${resp.status})`);
  }
  return resp.json();
}

// 方法名转小写做 CSS class
function methodCls(m) { return "m." + (m || "GET").toLowerCase().slice(0, 1).toUpperCase() + (m || "GET").toLowerCase().slice(1); }

function loadCases() {
  api("/api/cases").then((list) => {
    const tbody = document.querySelector("#case_table tbody");
    tbody.innerHTML = list.map((c) => `
      <tr>
        <td>${c.name}</td>
        <td><span class="method ${methodCls(c.method)}">${c.method}</span></td>
        <td>${c.url}</td>
        <td>${c.source}</td>
        <td>${c.validates}</td>
      </tr>`).join("");
  }).catch((e) => setTip("加载用例失败：" + e.message, true));
}

function loadReports() {
  api("/api/reports").then((list) => {
    $("st_total").textContent = list[0] ? list[0].total : "-";
    $("st_passed").textContent = list[0] ? list[0].passed : "-";
    $("st_failed").textContent = list[0] ? list[0].failed : "-";
    $("st_rate").textContent = list[0] ? list[0].pass_rate + "%" : "-";

    const tbody = document.querySelector("#report_table tbody");
    tbody.innerHTML = list.map((r) => `
      <tr>
        <td>${r.report_id}</td>
        <td>${r.started_at}</td>
        <td>${r.passed}/${r.total}</td>
        <td>${r.pass_rate}%</td>
        <td>${r.duration}</td>
        <td>${r.gen_mode}</td>
        <td><a class="link" onclick="showReport('${r.report_id}')">查看</a></td>
      </tr>`).join("");
  }).catch(() => {});
}

function setTip(msg, isErr) {
  const t = $("tip");
  t.textContent = msg;
  t.style.color = isErr ? "#c0392b" : "#5a8f6a";
  setTimeout(() => { t.textContent = ""; }, 6000);
}

function showReport(rid) {
  api(`/api/reports/${rid}`).then((data) => {
    $("detail_panel").style.display = "block";
    $("detail_title").textContent = `报告详情 - ${data.report_id}（通过 ${data.passed}/${data.total}，${data.pass_rate}%）`;
    const rows = data.results.map((r) => {
      const cls = r.passed ? "pass" : (r.skip ? "skip" : "fail");
      const txt = r.passed ? "通过" : (r.skip ? "跳过" : "失败");
      return `<tr><td>${r.name}</td><td>${r.source}</td>
        <td><span class="tag ${cls}">${txt}</span></td>
        <td>${r.status_code}</td><td>${r.elapsed}</td>
        <td class="err">${(r.errors || []).join("\n") || (r.skip || "-")}</td></tr>`;
    }).join("");
    $("detail_body").innerHTML = `
      <table><thead><tr><th>用例</th><th>来源</th><th>结果</th><th>状态码</th><th>耗时</th><th>说明</th></tr></thead>
      <tbody>${rows}</tbody></table>`;
  }).catch((e) => setTip(e.message, true));
}

// 按钮事件
$("btn_run").addEventListener("click", () => {
  const btn = $("btn_run");
  btn.disabled = true;
  btn.textContent = "执行中...";
  api("/api/run", { method: "POST" }).then((r) => {
    setTip(`执行完成：通过 ${r.passed}/${r.total}（${r.pass_rate}%）`);
    loadReports();
  }).catch((e) => setTip("执行失败：" + e.message, true))
    .finally(() => { btn.disabled = false; btn.textContent = "▶ 执行测试"; });
});

$("btn_ai_gen").addEventListener("click", () => {
  setTip("AI 生成中，稍等...");
  api("/api/ai/gen", { method: "POST" }).then((r) => {
    setTip(`AI 生成完成：${r.count} 条（${r.gen_mode === "llm" ? "大模型生成" : "模板生成"}），文件 ${r.file}`);
    loadCases();
  }).catch((e) => setTip("AI 生成失败：" + e.message, true));
});

$("btn_ai_analyze").addEventListener("click", () => {
  setTip("AI 分析中，稍等...");
  api("/api/ai/analyze", { method: "POST" }).then((r) => {
    $("detail_panel").style.display = "block";
    $("detail_title").textContent = `AI Badcase 分析（失败 ${r.failed_count} 条，基于报告 ${r.report_id}）`;
    $("detail_body").innerHTML = `<div class="analysis">${r.analysis}</div>`;
  }).catch((e) => setTip("AI 分析失败：" + e.message, true));
});

// 初始化
loadCases();
loadReports();
