# 热搜话题演化聚类与舆论预警系统

基于题目要求实现的 Python 项目，包含：

- 话题快照数据生成（可替换为真实平台采集）
- 话题链提取（文本相似度 + 时间窗口约束，过滤寿命不足 6 小时）
- 基于 DTW 距离的时序聚类
- 演化模式识别与风险预警（重点关注“争议升级型”和“反转振荡型”）
- Flask 看板展示（预警列表、演化曲线、聚类分布）

## 目录结构

`app.py`：Flask 入口  
`src/data_simulator.py`：模拟数据  
`src/topic_chain.py`：话题链提取  
`src/analysis.py`：DTW 聚类与模式识别  
`src/alerts.py`：预警逻辑  
`templates/index.html`：前端页面  
`static/style.css`：样式

## 运行方式

1. 创建虚拟环境（可选）
2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 启动服务：

```bash
python app.py
```

4. 浏览器访问：

<http://127.0.0.1:5000>

## 后续可扩展

- 把 `generate_snapshots()` 替换成微博/知乎/B站实时采集
- 增加情绪模型（文本分类）替代模拟情绪值
- 用轮廓系数、Calinski-Harabasz 指标自动调优聚类数
- 将结果写入数据库并做增量实时更新
