# HeatSignal：高温冲击下的全球数字连接韧性

**英文工作标题：** Global digital connectivity resilience under heat stress  
**竞赛项目名：** HeatSignal — Keeping digital lifelines connected under heat stress  
**研究主题：** 高温韧性（heat resilience）；以数字连接为具体关键基础设施对象  
**研究类型：** 多国观测性事件研究、韧性分项比较与历史事件回放  
**方案版本：** 2026-10-07（高温韧性主线修订版）  
**范围：** 从 Judy 服务器已下载资料中择优使用，不补下载早期 ERA5，不依赖尚未取得的 Trinocular 或实时预报。现有数据和派生结果均须区分“文件存在”“通过检查”“具备分析资格”与“已完成正式统计分析”。

### 本次修订的核心

**研究不是“高温夜是否影响互联网”，而是“数字连接在多强、持续多久的高温冲击下，能保持多少功能、承受多大缺口、多久恢复，以及这些表现为何不同”。**

| 研究层次 | 主要问题 | 本版安排 |
|---|---|---|
| 高温冲击（输入） | 有多热、持续多久、多少居民暴露？ | 最高温度 Tmax、超阈强度、持续天数和累计热剂量为主 |
| 高温韧性（响应） | 能否维持连接，下降多深，持续多久，如何恢复？ | 功能保持率、峰值缺口、持续时间、DHRD及恢复确认时间分别报告 |
| 条件与解释 | 同等热冲击下，哪些条件伴随较好表现？ | 夜间降温/最低温、露点、社会经济和正常期连接状态为补充 |
| 社会意义 | 技术缺口与数字依赖人口如何叠加？ | DLEP作为暴露代理，不等同韧性评分或真实断网人数 |
| 未来压力（次级模块） | 现有模式情景中的高温压力怎样变化？ | 用已下载CMIP6作模式内气候压力比较，不预测未来断网次数 |

上一版偏重最低温，是为了检验“夜间冷却是否有助恢复”这一特定假设；它不应代替整个高温韧性主题。本版将该假设降为二级分析。主热事件仅由 Tmax 定义，纯 Tmin 超阈不能进入主事件样本，也不能延长主事件结束时间。

**统一限制：** 2018–2021为短期温度参考，不是长期气候正常值；2022–2025为 IODA 主观测期；日极值来自 UTC 小时资料，Tmax不一定发生在当地白天，Tmin也不等于精确夜温。研究测量的是宏观数字连接的短期抵抗与恢复，不直接识别设备故障、全部适应能力或气候变化因果效应。

---

## 1. Executive summary

高温韧性不仅是暴露于多少热量，更是系统在热冲击下保持功能、承受扰动并恢复的能力。数字连接支持风险预警、医疗信息、支付、工作与求助，却也可能承受冷却、供电和运行压力。本研究将数字连接作为高温韧性的具体对象，检验：**2022–2025年，最高温度的强度与持续过程是否伴随宏观连接功能下降；在可比高温冲击下，哪些国家或地区表现为缺口较浅、持续较短、恢复较快？**

主气象资料为服务器已下载的2018–2025年 ERA5 小时 t2m、d2m。逐像元计算 UTC 日最高/最低温度，再以固定2025年 WorldPop 人口权重聚合至国家。使用2018–2021年国家日序前后15天的 Tmax 90%分位阈值识别主热过程；主事件连续至少两日超阈，且在参考期最暖连续三个月内起始。阈值、暖季及空间权重在分析前冻结；全年、六个月暖季、绝对最高温及不同持续天数为预定敏感性。本方案衡量相对近期参考的暖季热压力，不把温和地区的相对偏热直接称为设备危险温度。

IODA Active Probing 为主要连接结果，BGP 和 Network Telescope 提供不同测量机制的核查。韧性以可解释的分项表示：高温期间维持接近常态连接的比例、最大连接缺口、缺口持续时间、累计 DHRD 和高温结束后的恢复确认时间。热暴露是输入，连接响应是结果；不能用“高温较少”证明系统韧性较高，也不能用互联网用户多证明韧性较低。国家比较需限定在热强度、持续天数、测量覆盖及前期连接状态具有共同支持的范围内，不发布未经支持的全球韧性总排名。

在此主框架内，较高 Tmin、较少夜间降温或较高露点是潜在压力修饰因素；检验其是否解释同等 Tmax 冲击下的恢复差异，不预设它们比最高温更重要。已有世界银行数据用于数字依赖、电力可及性、收入和城市化分层；已有降水、STOP主动断网与IBTrACS气旋资料用于混杂筛查；部分月份风场只作配对子样本稳健性。可用ADM1用于检验国家聚合是否掩盖空间差异。

主要设计为同国家非热窗口匹配、事件曲线和条件恢复分析。所有结果均为待检验的观测关联，允许无清晰平均关联或地区差异；多信号一致不自动构成因果识别。原型交付是历史高温—连接韧性回放和准备措施讨论卡。已下载CMIP6可支持次级的未来高温压力模块，但不将四年连接样本外推为未来真实中断或损失人数。

### Proposal-stage abstract

> Heat resilience concerns the ability to maintain and restore function under thermal stress, not exposure alone. We propose a multicountry observational study of digital connectivity during 2022–2025 using existing hourly ERA5 temperature and dew-point fields and IODA connectivity signals. Daily maximum temperature will define the primary heat exposure, including intensity, persistence and cumulative excess above fixed 2018–2021 short-reference thresholds. The primary cohort will include events beginning within each country's reference-defined warmest consecutive three months, with broader-season and absolute-temperature sensitivity analyses. Active Probing will be the primary outcome, with BGP and Network Telescope used for cross-signal checks. We will characterize functional maintenance, peak connectivity deficit, disruption duration, cumulative deficit and recovery confirmation after the defined Tmax event ends. Comparisons of resilience will be restricted to comparable heat loads and observation quality. Minimum temperature and reduced overnight cooling will be examined as secondary modifiers, alongside available meteorological and socioeconomic information. Existing shutdown and cyclone records will support confounding checks, and subnational observations will test aggregation sensitivity. A separate module may use already available CMIP6 simulations to characterize future heat pressure, without projecting outage counts. Outputs will support transparent historical event replay rather than validated advance warnings, equipment-failure attribution or estimates of individual disconnection.

正式摘要在分析后补充实际国家/事件数、效应量、区间及支持范围，不将上述假设写成发现。

---

## 2. 标题与核心主张

### 2.1 论文工作标题

**Global digital connectivity resilience under heat stress**  
**高温冲击下的全球数字连接韧性**

标题保持中性，不预设必然断网，也不把夜间恢复作为唯一主题。只有最终证据支持时，才在副标题强调 prolonged heat、unequal recovery 或其他实际发现；不再使用“No night to recover”作为当前主标题。

### 2.2 一句话科学问题

> 在可比的高温强度和持续时间下，数字连接能保持多少功能、承受多大缺口、多久恢复；夜间降温、既有连接状态与社会条件是否与这些差异相关？

### 2.3 一句话竞赛主张

> HeatSignal 将高温暴露与数字连接的保持、损失和恢复放在同一张证据图上，帮助识别值得进一步核查的薄弱环节并讨论备用通信准备。

这不是对实时预警能力或干预有效性的既成声明。

---

## 3. 高温韧性叙事与概念边界

本文按以下次序展开，而不是围绕单一温度变量组织：

1. **高温冲击：** Tmax偏高多少、持续多久、哪些居民暴露。
2. **功能保持与抵抗：** 信号是否接近正常参照，最大下降多大。
3. **持续与恢复：** 缺口持续多久，高温结束后能否确认稳定恢复。
4. **可比条件下的差异：** 控制或分层热负荷与测量质量后，差异是否仍存在。
5. **解释与应用：** 结合夜间降温、露点、连接基础状态及社会条件讨论可能因素；展示历史证据与准备措施。

温度、人口暴露、社会依赖和韧性表现必须分开。较热地区并不必然缺乏韧性；相同缺口也可能对应不同暴露人口。DHRD是响应的综合量度，不是单独足以概括全部韧性的总分；DLEP是社会加权代理，不作为韧性高低排序。

工程路径“高温 → 设备/冷却/供电或运维压力 → 连接变化”具有研究动机，但当前资料未直接观测这些中介。世界银行电力可及性不是事件级停电记录，收入和城市化不是实际应急能力测量。本文聚焦**观测到的短期抵抗与恢复表现**，不声称测量了系统的全部适应、学习和转型能力。

---

## 4. Research gap

### 4.1 文献背景：从基础设施功能到高温韧性

以下沿用前版已收录文献，按当前问题重新组织，不声称本次已完成新的系统检索。

**高温与关键基础设施。** 热浪—电网故障复合风险、极端天气下的电力充足性、制冷需求和负荷研究，为“冲击强度与系统功能”提供研究背景；它们不能直接证明互联网在高温下发生同样的机制：

- [Compound Climate and Infrastructure Events: How Electrical Grid Failure Alters Heat Wave Risk](https://doi.org/10.1021/acs.est.1c01209)
- [Spatiotemporal assessment of renewable adequacy during diverse extreme weather events in China](https://doi.org/10.1038/s41467-025-60264-9)
- [Efficiency-weighted cooling degree days reveal opposing temperature and humidity effects on energy demand](https://doi.org/10.1038/s41467-026-75388-9)
- [Electricity load forecasting under extreme heat and cold waves](https://doi.org/10.1038/s41467-026-77014-0)

**数字连接的观测与气候风险。** 天气与住宅网络连接、互联网中断/主动断网分类、通信资产气候暴露及ITU适应文件，分别帮助构建结果测量、排除审查和工程动机。资产暴露、工程可能性和实际连接恢复不是同一种证据：

- [Residential Links Under the Weather](https://www.cs.umd.edu/users/dml/papers/weather_sigcomm19.pdf)
- [Destination Unreachable: Characterizing Internet Outages and Shutdowns](https://estcarisimo.github.io/assets/pdf/papers/2023-sigcomm-shutdowns.pdf)
- [Global vulnerability assessment of mobile telecommunications infrastructure to climate hazards using crowdsourced open data](https://www.nature.com/articles/s41467-026-76197-w)
- [ITU overview on adaptation to climate change for ICT networks](https://www.itu.int/epublications/en/publication/itu-t-l-suppl-49-2022-07-overview-on-adaptation-to-climate-change-for-information-and-communication-technology-networks/en)

**热暴露的补充维度。** 热夜及昼夜复合热浪的健康文献为次级Tmin假设提供背景，但健康结局不能直接外推为通信设备响应；本研究也不因此把最低温置于Tmax主热负荷之前：

- [Short-term association between hot nights and mortality: a multicountry analysis in 178 locations](https://pubmed.ncbi.nlm.nih.gov/40882422/)
- [Nonlinear exposure–response associations of daytime, nighttime, and day–night compound heatwaves with mortality](https://www.nature.com/articles/s41467-025-56067-7)

### 4.2 本研究的切入点

上述背景沿用前版文献记录。此前检索偏重热夜，不足以支撑“更广义的高温与数字韧性从无人研究”的断言；投稿前需按 Tmax、heatwave intensity/duration、connectivity resistance/recovery 等重新更新检索。

本研究的工作性切入点是：在同一套多国观测框架下，把**高温负荷、连接功能保持、扰动持续与恢复**分开量化，并检验同等热负荷下的韧性差异；再考察夜间降温和社会数字依赖提供什么额外信息。研究价值依赖可复核的动态证据和比较设计，不依赖“最低温一定比最高温重要”或“首次研究”的宣传。

### 4.3 预期贡献

1. 将数字连接从高温适应工具扩展为需要保持功能与恢复的关键基础设施对象。
2. 建立Tmax主导的高温事件—连接响应目录及抵抗、持续、恢复分项。
3. 使用已有多信号及可匹配ADM1核查测量和尺度，并明确比较的共同支持边界。
4. 区分韧性响应、居民热暴露和数字依赖加权后果，为高温准备讨论提供可解释证据。

---

## 5. 研究问题、假设与可证伪条件

### RQ1：高温强度和持续时间与连接功能保持有何关系？

**H1：** 在季节、时间规律和可用气象条件调整后，更强或更持久的Tmax热冲击可能伴随较低功能保持率、较大峰值缺口或较长缺口持续时间。

主问题先比较Tmax热事件与匹配非热窗口，再估计事件内强度—持续响应。峰值高和持续长是不同特征；不得因累计热剂量大就断言单位时间损失更强。相对热阈值和事件绝对最高温同时报告。

### RQ2：系统能承受多少连接扰动，如何恢复？

**H2：** 相似Tmax冲击可对应不同抵抗与恢复组合：缺口较浅但恢复较慢、缺口较深但恢复较快，或未检测到显著缺口。检验分项，不预设单一总分能排列韧性。

以高温过程最后一个 Tmax 超阈日结束作为统一恢复锚点；Tmin偏高不延后该锚点。恢复仅在受损条件样本中估计，同时报告所有热事件的保持率、受损比例、待确认/延迟缺口及删失。

### RQ3：哪些条件与高温韧性差异相关？

**H3：** 在有共同热暴露与测量支持的范围内，事件前连接稳定性、电力可及性、收入或城市化可能修饰响应。条件差异不能自动归因于适应政策、设备质量或真实备用电力。

跨国图表展示调整范围、区间和样本覆盖；数据不足或热暴露无重叠的国家不强制排名。

### RQ4：夜间降温和湿度是否提供额外解释？

**H4（次级）：** 在Tmax主热负荷之外，较高Tmin/连续热夜或较高露点可能伴随恢复较慢。Tmin仅为修饰因素，不决定主事件入选与结束，不要求它一定优于最高温。

UTC日最低温只代理夜间冷却。真正当地夜间与小时滞后解释需经太阳日/现有ADM1检验；最高与最低温的强相关须报告，不把增量解释力当作机制证明。

### RQ5：技术响应与数字依赖加权暴露是否一致？

**H5：** 较小的技术缺口可能因数字依赖人口较多而对应较大的DLEP。该问题衡量后果权重而非重定义韧性，不能解释为真实断网人时。

### 次级未来问题与证据门槛

在已下载模式内部，未来Tmax超阈热日、持续天数与热剂量是否改变？这只回答未来压力，不回答未来韧性或中断次数。

所有H1–H5都允许不成立。主结果需结合区间、实际量级、前趋势、多信号、留一地区及短参考敏感性判断；无显著结果不构成失败，事后挑选地区或夜间指标不能挽救不成立的主张。

---

## 6. 高温冲击与韧性指标

### 6.1 主热暴露：Tmax、强度、持续时间与累计热剂量

令 \(i\) 为ERA5像元，\(h\) 为小时，\(d\) 为UTC日期。温度从K转为°C：

\[
T^{max}_{i,d}=\max_{h\in d}T_{i,h},\qquad
T^{min}_{i,d}=\min_{h\in d}T_{i,h},
\]
\[
T^{max}_{c,d}=\sum_iw^{2025}_{ci}T^{max}_{i,d},\qquad
T^{min}_{c,d}=\sum_iw^{2025}_{ci}T^{min}_{i,d}.
\]

使用固定2025年人口权重，先像元内取日极值再聚合，不能改成先平均国家小时温度再取极值。0.25°权重重新构建；海岸/国界采用原人口像元中心分配，是人口栅格分辨率上的近似，保存未分配与重叠审计。缺失小时不插值制造完整日，不以静默人口重归一化掩盖缺覆盖。

**冻结Tmax短参考阈值：**

\[
q^{max}_{c,j}=Q_{0.90}\{T^{max}_{c,d}:
\operatorname{year}(d)\in[2018,2021],
\operatorname{dist}_{365}(\operatorname{doy}(d),j)\le15\},
\]
\[
E^{max}_{c,d}=[T^{max}_{c,d}-q^{max}_{c,\operatorname{doy}(d)}]_+,\qquad
H_{c,d}=1[T^{max}_{c,d}>q^{max}_{c,\operatorname{doy}(d)}].
\]

在8.5定义的Tmax事件内，保存：

- \(I^{peak}_{c,e}=\max_{d\in e}E^{max}_{c,d}\)：最高超阈强度，°C；
- \(I^{mean}_{c,e}\)：核心超阈日的平均超阈强度，°C；
- \(L^{hot}_{c,e}=\sum_{d\in e}H_{c,d}\)：超阈天数，并另存最长连续段与含桥接日的总跨度；
- \(HD_{c,e}=\sum_{d\in e}E^{max}_{c,d}\)：累计热剂量，°C-days；
- 事件绝对最高温 \(\max_{d\in e}T^{max}_{c,d}\)、像元超阈人口比例（空间敏感性）。

新记号HD替代前版DHD，突出“最高温热剂量”而非假定UTC峰值一定在当地白天。对相同超阈日集合，HD与平均强度×热日数存在确定关系，不能把三者全部放进同一线性模型并解释为独立效应。

使用365日循环日历；估阈值剔除2月29日，闰日分析阈值为相邻两日阈值均值。每个日序约124个候选日且有序列相关；至少90%候选日有效且四年均有贡献才估主阈值。记录分位数插值方法。四年逐年剔除和年块诊断用于显示不稳定性，不能给出可信的长期气候不确定性。

这是2018–2021**短期参考**，不是30年气候正常值，不支持长期极端或变暖归因。[WMO climatological normals](https://wmo.int/wmo-climatological-normals) Tmax和Tmin本来对应不同热指标；例如Climdex分别定义最高温暖日指标与最低温暖夜指标，不能把两者视为同一问题。本方案的两日、31日窗口和短参考是研究自定义，并非标准WSDI实现。[Climdex indices](https://www.climdex.org/learn/indices/)

### 6.2 次级热条件：Tmin与露点

按相同日序方法估 \(q^{min}_{c,j}\)，在**已由Tmax确定的事件窗**计算：

\[
NTRD_{c,e}=\sum_{d\in e}[T^{min}_{c,d}-q^{min}_{c,\operatorname{doy}(d)}]_+.
\]

同时保存Tmin超阈日数/占主事件天数比例；NTRD沿用前版记号，但定位为最低温度热剂量／夜间降温不足代理，而不是主冲击。可用Tmax与Tmin差值描述日温差，但不可同时把Tmax、Tmin及其差值作为独立线性解释变量。

日均露点来自同小时 d2m后聚合，用于湿润条件调整或预定交互。若研究相对湿度，则从小时 t2m/d2m按记录清楚的相态公式计算后聚合；不把人体热指数视为设备热耐受阈值。没有全期风与辐射，不构建需要这些输入的完整室外热应激指标作为主变量。

主要暴露始终是Tmax强度和持续性。NTRD或露点未提供额外信息时，保留H1–H3主分析，不因此否定整个高温韧性研究。

### 6.3 连接参照基线（仅供回顾性分析）

Active Probing 保留10分钟间隔；BGP、Telescope 的5分钟数值按两个完整有效槽的均值聚合为10分钟，缺槽记缺失。统一 UTC 时点、相同星期与时刻建立参照：

\[
\widehat C_{c,s,t}=
\operatorname{median}\{C_{c,s,t\pm7k\ {\rm days}}:k=1,2,3,4\}.
\]

排除全年Tmax目录中所有已识别热过程及其72小时恢复窗（不限于主暖季入选事件）、已知主动断网、气旋影响和确认的测量异常。最多8个候选中至少4个有效且前后各至少1个，参照必须大于零；不满足则该时点缺失。首尾不足使可分析日期范围收缩，不缩短已经定义的事件及其后72小时主DHRD积分窗；不完整窗口退出主积分分析，恢复随访的删失另按6.6处理。基线资格、异常筛选参数及稳健性方案须在效应估计前冻结。

这是包含未来观测的**回顾性参照**，不是已识别的无高温因果反事实。尾随28天、只用过去的参照作敏感性；其观测覆盖另行报告，不能把两种基线混合。实际前瞻预测还需当时可用的预测气象输入，本轮未提供。

### 6.4 连接缺口与有符号偏离

\[
r_{c,s,t}=C_{c,s,t}/\widehat C_{c,s,t}-1,\qquad
g_{c,s,t}=\max(0,-r_{c,s,t}).
\]

\(g=0.10\) 表示该信号低于参照10%，不是10%人口断网。因截断缺口在正常波动下也可能为正，主事件曲线同时报告有符号偏离 \(r\)，并与非热匹配窗口比较；不把正 DHRD 本身当作高温损失证据。

### 6.5 Digital Heat Resilience Deficit：DHRD

\[
DHRD_{c,s,e}=
\sum_{t=t_{\rm start}}^{t_{\rm end}+72h}g_{c,s,t}\Delta t,\qquad
\Delta t=1/6\ {\rm hour}.
\]

\(t_{\rm end}\) 为Tmax分析事件最后一个核心超阈日结束的排他时刻；积分包含事件跨度（桥接日另标）及其后72小时，为左闭右开。这个时点不意味着所有热压力或湿热均已消失。单位为 connectivity-deficit hours。10%缺口持续10小时和20%持续5小时均为1 deficit-hour，故需结合分项指标。

主 DHRD 要求整个积分窗口都有有效信号和参照；不把缺失当零。扩展样本可报告“观测到的缺口积分”和覆盖率，但不得与完整窗 DHRD 混算。事件长短同时影响总量，另报每小时缺口并在事件模型中调整热过程长度。

### 6.6 功能保持、抵抗、持续与恢复

事件期 \(W_e=[t_{\rm start},t_{\rm end})\) 包含已标记的桥接日；实际Tmax超阈日另存。主抵抗指标限于 \(W_e\)，不把72小时后的延迟缺口混称事件期抵抗：

\[
Maintenance_{c,s,e}=
|W_e|^{-1}\sum_{t\in W_e}1[C_{c,s,t}/\widehat C_{c,s,t}\ge0.95],
\qquad
PeakLoss^{core}_{c,s,e}=\max_{t\in W_e}g_{c,s,t}.
\]

\(|W_e|\) 为10分钟槽数。Maintenance是接近参照的观测槽比例，不是服务可用率SLA或“95%人口保持联网”。另报事件期平均缺口、有符号偏离；将指标限定在实际超阈日作为敏感性。

- **Disruption duration：** 事件期及之后72小时中 \(C/\widehat C<0.95\) 的累计小时数，分期另报。
- **Peak loss, full window：** 核心期加72小时的最大缺口，作为延迟失效补充，不代替核心抵抗指标。
- **DHRD及每小时缺口：** 同时报累计积分和除以完整观察时长的均值，避免长事件机械地产生较大总量。
- **Recovery confirmation time：** 从最后Tmax核心日结束起，到连续24个10分钟槽均达到 \(C/\widehat C\ge0.95\) 的确认完成时刻。确认段起点可另作描述，主删失分析使用确认时间。

对有完整观察的事件作互斥分类，结束状态取 \(t_{\rm end}\) 前最后一个有效槽：（1）核心期未低于95%，后续也未低于：全窗无显著缺口；（2）核心期未低于95%，后续出现缺口：延迟发生；（3）核心期有缺口且结束时仍低于95%：结束时受损，不论之前是否短暂恢复；（4）核心期有缺口、结束时达95%，且最后连续24槽均达标：结束前稳定恢复；（5）核心期有缺口、结束时达95%但最后24槽未全部达标：待确认。恢复后再次缺口另设复发标记，不重复计入类别。缺失导致核心/结束状态或后续无法判定者单列“观察不足”，不得默认无缺口。

主条件生存分析只纳入第（3）类，“待确认”另作补充。全体事件状态比例和观察不足数量必须一并报告，不能只展示恢复较快的子集。

72小时尚未完成确认者右删失；资料提前结束或缺测另记行政/缺测删失及最后可确认时点，不称“已知72小时未恢复”。90%/98%门槛和2/6小时确认长度为敏感性。Tmin或露点在后续仍偏高可以作为描述或预定补充条件，但不改变主事件终点。

### 6.7 数字生命线暴露代理量 DLEP

\[
DLEP_{c,e}=DHRD_{c,\mathrm{AP},e}\times Population_c^{2025}
\times InternetUseShare_{c,y}.
\]

人口为固定2025基准，互联网使用占比优先事件当年，否则仅用三年以内最近过去值并标记；IT.NET.USER.ZS 原值为百分数，必须除以100转成0–1的 InternetUseShare。无值则 DLEP 缺失，但可保留技术缺口分析。DLEP 是按统一人口基准的互联网用户加权缺口代理，不是历史真实受影响人数或人时，不作福利损失估计。

---

## 7. 现有数据的选择与用途

### 7.1 为什么选择这些旧数据

数据按其在“高温冲击—韧性响应”中的作用选用，不因为已经下载就全部入模。四层安排如下：

| 层级 | 选择的数据 | 目的 |
|---|---|---|
| 主分析输入与结果 | ERA5小时Tmax及露点、IODA AP、WorldPop2025、CGAZ边界 | 定义热强度/持续与人口暴露，观察连接保持及恢复 |
| 主分析质量和混杂审查 | 已有ERA5-Land降水、STOP、IBTrACS、IODA历史人工核查事件目录 | 筛查降雨、气旋、主动断网及测量异常；不伪称完全消除混杂 |
| 次级解释与验证 | ERA5 Tmin、BGP/Telescope、可靠ADM1、世界银行、有限月份风场 | 夜间条件、跨信号/空间核查、社会条件分层及配对稳健性 |
| 独立次级/暂不纳入 | 已下载CMIP6用于未来热压力；旧RIPE重建与未取得Trinocular不进主面板 | 区分未来气候、测量研究和当前观测证据 |

### 7.2 原始文件与实际覆盖

| 模块 | 现有内容与时期 | 本版用途与限制 |
|---|---|---|
| ERA5 主气象 | GSC2027/era5，2018–2025，96个月，t2m/d2m，小时0.25°，共211,393,886,508字节 | Tmax主热冲击、露点及次级Tmin；不是 ERA5-Land |
| ERA5-Land 降水 | 2018–2025月份已齐；97个文件含2026-01-01单时点边界文件 | 经累计量与 UTC 日标签审计后作协变量，保持独立来源 |
| ERA5-Land 风场 | 2024年1–3月及7月日均 u10/v10 | 仅已有月份完整窗口的配对子样本稳健性 |
| 旧温度数据 | 部分 ERA5-Land Tmin/Tmax；旧小时温度队列仅部分完成 | 不拼接主温度序列，不要求补齐旧队列 |
| IODA 国家 | 2288个缓存响应文件已核验；2022–2025有观测 | AP主结果，BGP/Telescope交叉核查；早期空响应不是零中断 |
| IODA ADM1 | 六国4512个缓存响应文件，其中2242含series、2270为空 | 仅可靠匹配的次国家探索性分析 |
| 人口与边界 | WorldPop 2025全球1km；现有 CGAZ ADM0/ADM1 | 固定人口权重；代码、属地与争议地区需人工对照 |
| 世界银行 | 2018–2025现有国家—年表 | 数字依赖和异质性，缺失保留 |
| STOP | 已下载主动断网事件表 | 日期、地区和名称清洗后排除/标记 |
| IBTrACS | 52,766轨迹点、882个SID的现有表 | 经经度与时间检查后筛查气旋混杂 |
| NEX-GDDP-CMIP6 | 10模型、合计2320文件（full_v2为2318，另有2个pilot文件） | 次级模式内高温压力模块，不进入历史连接主模型或未来中断预测 |

本表“已核验”不等于所有分析资格审查完成。新 ERA5 的96个文件均能打开，变量、维度、单位、整月小时数和3600秒步长已通过检查；三个代表月做过数值抽查。尚未完成全部像元值扫描和全量 SHA-256 清单，后续按分块处理同步记录。现有文件无 .part；历史队列另有未完成下载，不属于这96个文件。

### 7.3 IODA：只分析真实可观测时期

国家和六国 ADM1 的2018–2021年公共端点此前返回成功但无三类核心观测，故不构造该时期连接面板。2022–2025年也须按国家—信号—年份重新筛选；文件存在不等于有效覆盖。2024年粗覆盖审计中 AP 有244个、BGP有252个、Telescope有167个实体达到80%观测率，这些只是单年初筛数，不能直接写为最终国家样本。

AP 表征主动探测可达性；BGP 表征路由可见性；Telescope 反映非请求流量。不同信号分别标准化和分析，不直接相加。三者属于同一平台，不称完全独立观测系统。另有1704条IODA历史人工核查事件，可作为重大异常的核对目录，不当作连续信号或与热无关的独立结局；其确切时间覆盖与标签定义进入使用前审核。不用 alert score、空响应或预测值替代真实观测。[IODA resource hub](https://ioda.inetintel.cc.gatech.edu/resources?tab=repositories)

Trinocular 截至本次审查仍未作为可用原始数据入库。原访问申请保留历史记录，但不进入当前数据流、样本、结果、时间表或核心交付；本版不发起新的访问或下载。如果以后另行取得，须重新设计跨测量系统复核，不能与 IODA 拼接，也不能自动声称对重叠参考期的样本外验证。

### 7.4 主气候：ERA5 小时温度和露点

服务器路径：/volume1/homes/Judy/GSC2027/era5。文件由 era5_2m_201801.nc 至 era5_2m_202512.nc；维度为 valid_time × latitude × longitude，纬度90至−90、经度−180至179.75，721×1440，t2m/d2m 为 K。时间坐标是自1970-01-01起的秒；不得误按小时解析或假定经度为0–360。[ERA5 single levels documentation](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels?tab=documentation)

采用 UTC 00:00–23:00 的24小时主日，方便与 IODA 和已有日降水对齐。主湿度协变量使用人口加权日均露点，单位 °C；相对湿度如开展，必须从同小时 t2m/d2m 用记录清楚的相态公式推导后再聚合，不能拿日均温度和露点代替小时关系。湿球温度、热指数不作为核心依赖。

本轮不再走 GEE 导出或重新请求 CDS。已有0.1°温度和0.25°ERA5不可混拼。主权重必须按0.25°网格重建，不能复用旧0.1°索引。

### 7.5 已有降水与风场

降水来自 ERA5-Land，与主温度来源及网格不同。按该批文件的产品和累计属性明确日归属：对标准日累计输出，00 UTC值通常属于前一日累计；若文件已去累计或已做日聚合则不能再次平移。检查元数据、已有下载脚本及边界日后冻结转换，m转换为mm，负异常和缺日留审计记录。[ECMWF ERA5-Land documentation](https://confluence.ecmwf.int/pages/viewpage.action?pageId=501029136)

在其自身0.1°网格上用同一人口基准聚合至国家—UTC日，再按国家和日期连接；不伪称原始同网格。降水质量不通过的国家—日期从需要该控制的主模型剔除，缺测不当零；另外报告不含降水的更大样本。比较协变量增量时固定同一样本。

风场仅覆盖已有2024年1–3月和7月。若源变量为日均 u/v，则 \(\sqrt{\bar u^2+\bar v^2}\) 是日均风矢量模长，不是平均瞬时风速或阵风；不能据此排除全期强风。只对气象/连接窗口完整且具有足够对照的事件比较有风与无风模型，若不足则不估计并报告原因。

### 7.6 人口、行政边界与 crosswalk

WorldPop 2025固定用于所有参考年与分析年，表征统一人口分布下的居民热暴露，不代表历史人口变化或通信设备位置。栅格聚合采用人口守恒的分配，海岸与边界交叠单元需记录；权重缺覆盖不能当零人口。

现有 CGAZ ADM0 有218个单元，ADM1有3224个单元，其中争议区域等存在数字代码。既有气候 crosswalk 只有195个精确匹配、23个未匹配单元，不能用名称近似自动合并。维护 IODA ISO2—边界ISO3—World Bank代码映射及争议/属地规则，保留未匹配清单。ADM1 仅限现有六国、几何和代码都可靠的子样本，不承诺全球次国家覆盖。

### 7.7 世界银行社会经济指标

使用 IT.NET.USER.ZS（互联网使用）、EG.ELC.ACCS.ZS（电力可及性）、SP.URB.TOTL.IN.ZS（城市化）及 NY.GDP.PCAP.PP.KD（PPP人均GDP）。现有1736行国家—年表有明显缺失；初审电力231行、互联网446行、GDP164行缺值；尤其2025年电力指标0/217、互联网使用仅10/217有值，不能默认“有2025表”就是2025全覆盖。韧性修饰变量优先采用事件年份之前、三年以内最近可用的年度值，避免将年度同步变化解释为先在能力；DLEP作为回顾性描述可按6.7使用当年或最近过去值。保存年份和填补标记，不用未来值、不无条件插值。电力可及性不等于供电可靠性，GDP不等于实际应急能力；每个模型报告独立可用样本。

### 7.8 主动断网与气旋

STOP 现有2102条记录中713条结束日期空缺，另有2条无效日期、3条先后倒置、180条名称未匹配，需先做标准化。使用geo_scope、area_name和shutdown_extent等地理字段清洗。已明确地区与日期的中断若与分析窗重叠，按目标聚合层级保守筛查；局地事件不得自动标成无限期全国中断。结束未知者：主分析标记起始日、人工核对与热事件重叠的高风险记录；±7日、±30日排除窗作敏感性，不把假设结束日当已知事实。无法确定的重叠单列不确定样本。

IBTrACS 先将超过180°的经度规范化并处理日期变更线。预定筛查可用轨迹距边界300km、轨迹时点前后各24小时作为候选影响窗，100/500km和±72小时为敏感性；这只是保守气旋混杂标记，不是实际灾害受损范围。大国增加可靠 ADM1 检查。STOP 和 IBTrACS 都不能穷尽维护、停电、非气旋强风和局地冲击。

### 7.9 Judy 计算环境与资源约束

已建立 judy conda 环境，Python 3.11.16；常用数组、气候、地理和统计库导入及依赖检查已通过。登录后 conda activate judy；若非交互会话不自动初始化，调用该环境的 Python 或已有 conda 初始化方式，不另建重复环境。锁定实际包版本与脚本配置后再处理。

服务器约3.8 GiB内存、4逻辑CPU。一个完整月两变量解压后约6 GB，禁止把全年或整月全球两变量直接载入内存。按月、空间小块和必要小时块读取，先算局部每日统计并累加稀疏人口权重，输出国家—日小表；限制并发，观察峰值内存并支持检查点。正式运行前用一个已下载月验证时间口径、权重守恒及分块/直接小样本计算一致性。可选库未安装不作为重新配置环境的理由，优先用已有库实现必要分析。

### 7.10 已有 CMIP6：次级未来高温压力模块

已下载10模型资料，full_v2目录2318个NetCDF，另有2个MIROC6试点文件，总清单2320；具体年份与试点复用关系必须按清单合并去重，不能仅看目录计数。历史段为1991–2014，情景段包括2015–2020及2041–2060、2081–2100，分别记录SSP2-4.5/SSP5-8.5。

主论文历史关联不依赖该模块，但服务器已有资料可以回答“未来外部高温压力是否增大”。通过完整性、日历、单位和网格审查后，在每个模式自己的既有1991–2020参考内估Tmax阈值，比较未来热日频率、连续段长度、峰值和累计热剂量，并分别展示绝对最高温。历史与情景拼接用于模式参考，来源和情景差异必须公开；它不是补下载ERA5的要求，也不是主历史研究的观测阈值。固定模型参考期暖季，不随未来温度重新挑季节；全年作为敏感性。

输出多模型分布及覆盖，不把模式未来温度直接减ERA5四年阈值，不把短历史关联外推为未来DHRD、断网次数或人数。模式日定义与ERA5口径未证实一致时，只给模式内部变化，不做历史观测值与模式绝对值的直接比较。若不足以支撑这些指标，则只报告模式内Tmax变化或省略模块，不新增下载。

### 7.11 已有资料的定位索引

以下路径均位于 /volume1/homes/Judy/GSC2027/HeatSignal/，主ERA5例外。2026-10-11 项目目录迁移后，旧 /volume1/homes/Judy/HeatSignal 为兼容符号链接：

| 资料 | 服务器相对路径 |
|---|---|
| 主ERA5小时温度/露点 | /volume1/homes/Judy/GSC2027/era5 |
| IODA国家与年度覆盖 | data/ioda/raw_core_signals/；data/ioda/year_source_availability.csv |
| 六国ADM1连接 | data/ioda/adm1_six_countries/ |
| 人口与边界 | data/worldpop/global_pop_2025_CN_1km_R2025A_v1.tif；data/boundaries/geoBoundariesCGAZ_ADM0.gpkg及ADM1.gpkg |
| 世界银行 | data/worldbank/country_year_indicators_2018_2025.csv |
| 降水与风 | data/weather_controls/raw_monthly/；data/weather_controls/global_pilot_2024_07/ |
| 主动断网 | data/stop/STOP_combined_2016_2025.csv |
| 气旋 | data/ibtracs/ibtracs_2018_2025_UTC.csv |
| 已调查的连接异常事件 | data/ioda/historical_event_catalogue/ioda_investigated_outages_cleaned_phase1+2.csv |
| 旧气象产品 | data/era5_land/raw_monthly/；data/era5_land/global_pilot_2024_07/ |
| CMIP6完整索引需同时纳入 | data/cmip6/full_v2/；data/nex_gddp_cmip6/pilot_MIROC6_ssp585_2050/ |
| 本轮运行输出 | analysis/2026-10-06_era5_existing_data/country_daily/ |

上述文件“在服务器”不代表直接可入模，必须完成对应代码、日期、质量与权限核查。

### 7.12 旧试算和重建数据的使用边界

已有RIPE Atlas及连接重建实验资料属于测量与重建路线，不等于新获得的连续IODA观测。现有六网络验证未通过全部门槛，不能据此批准历史回填。除非其中某条实际测量在时间、位置、单位和运行稳定性上与案例匹配并单独审核，不纳入本轮主分析或默认“独立验证”；插补/预测连接值绝不替代真实AP结局。2026-10-03旧气候/连接试算仅用于流程参考，不作为最终Tmax定义下的结果。

---

## 8. 样本构建与数据工程

### 8.1 分析范围

- 温度阈值参考：2018-01-01至2021-12-31，仅气象参考，不假定有该时期连接结果。
- IODA 目标分析：2022-01-01至2025-12-31；实际起止由信号质量、前后参照与恢复窗口共同确定。
- 主空间单元：通过 crosswalk、人口覆盖及信号资格审查的国家或地区。
- 主时间单元：国家×10分钟；热暴露为国家×UTC日；统计推断不得把重复的10分钟观测当作大量独立气象样本。
- 探索性 ADM1：现有美国、俄罗斯、加拿大、澳大利亚、巴西和中国数据中的可靠可匹配单元。
- 最终国家数、事件数、气候区覆盖均由预定筛选得出，不把253个来源实体或244个单年通过实体当成主样本承诺。

### 8.2 执行顺序

已有文件清单与软件版本 → 0.25°人口权重及代码映射 → 分块生成2018–2025国家—日Tmax/Tmin/露点 → 已有降水审计和合并 → 冻结2018–2021 Tmax阈值与暖季 → 2022–2025 Tmax主热事件 → IODA质量/参照与排除标记 → 完整事件面板 → 统计模型、图表和历史回放。

原始文件保持只读；每一步记录输入哈希、配置、行数、缺失和输出哈希。先完成一个月的小规模一致性测试，再顺序处理全期。当前文档修订不表示上述管线已经运行。

### 8.3 连接分析资格

每个国家—信号—年份至少80%原始有效率才进入候选。事件还需有合格的参照、可观察前趋势及恢复窗口；主 DHRD 采用完整积分窗。长时间近零、测量口径跳变、异常变异的序列先标记审查，不把低覆盖国家解释成低风险。

主 AP 样本和跨信号验证共同样本分别报告；BGP/Telescope不足不填补，不能只选择结果一致的国家。效应比较固定共同样本，另报各信号最大可用样本。公布从来源实体到最终分析窗的逐项排除漏斗与 observability 分层，但不把 observability 合进 DHRD。

### 8.4 同步异常和测量变更

每时点计算国家信号相对前一日同刻下降超过20%的比例；超过该信号经验99.9%分位的时点只标为“同步异常候选”，不能自动认定测量故障。结合跨洲分布、信号间差异、现有平台日志/记录及持续时间复核；只有有依据的测量异常在主样本剔除，无法判断者作单独敏感性。记录设备/测量覆盖口径变化，避免把真实跨国网络事件一律删掉。

### 8.5 主热过程：只有Tmax决定事件

先在全年构建Tmax目录，判定 \(T^{max}_{c,d}>q^{max}_{c,\operatorname{doy}(d)}\)，连续至少两日为原始过程。两个过程之间只有一个非热日时可合并，桥接日标记为非超阈，不将过程跨度冒充连续热日数。**Tmin-only事件不属于主热事件，Tmin不得触发、延长或合并Tmax过程。** 在既定Tmax事件内，可标记Tmin也偏高/未偏高，作为次级分层。

为避免将相对暖冬自动解释成高温灾害，预定义暖季：用2018–2021每日国家Tmax，计算12种循环连续三个月窗口的日数加权均值，选最高窗口；跨12月处理，并列按最早起始月份固定决定。主目标为在这个窗口起始的Tmax事件，跨月过程保留完整。暖季选择在分析期之前冻结，不依据连接结果调节；弱季节性地区报告参考年留一后的窗口稳定性。

先完成全年过程与8.6并组，再按最终事件最早起始日的暖季标签筛主样本；全年目录仍用于参照剔除、重叠检查和全年敏感性。六个月最暖循环窗口与全年是预定敏感性。每个地区报告事件绝对Tmax；冷凉地区相对偏热不必具有危险绝对温度，研究结论限于其实际支持范围。

Q95、连续三日/六日、绝对Tmax>30°C/35°C分别重建事件，不宣称两日定义是标准WSDI，不把30/35°C当全球统一损坏阈值。无足够事件或非热对照的地区标为不可估计。最低温>20/25°C只作为热夜次级指标的敏感性，不替代Tmax主事件目录。

### 8.6 分析事件、核心窗口与去重

原始Tmax过程保留独立目录；分析阶段将相隔少于7个完整非热日的核心过程并组，标记其中的热日、非热桥接日、最长连续段及总跨度。并组仍只依据Tmax，不能以夜间温度延长。终点为最后Tmax核心超阈日结束。HD对跨度内正超阈累计，桥接日按实际值计零；NTRD只在同一固定跨度内计算。

即使并组后，±7日估计窗口仍可能重叠。主堆叠样本只保留其[-7,+7]日及结束后72小时恢复窗不与其他全年Tmax事件核心/恢复段交叠的孤立事件。长过程保留描述及可行完整积分，不强求进入同一事件曲线；+7日仍在事件期时不能标为“已恢复期”。

非热对照必须没有Tmax主目录中的核心或恢复段，并满足相同质量规则。它可以出现Tmin相对偏高，基线/匹配中明确这一可能；次级检验可进一步限制Tmin条件，但不能偷偷改变主对照以强化夜间结论。对重复使用的对照日期记录次数并使总权重归一。报告因完整/孤立事件筛选损失的国家、暖季与热负荷，避免把容易观察的孤立事件外推为全部高温风险。

---

## 9. 高温韧性的统计比较

### 9.1 分析顺序与估计对象

先检验Tmax主热事件相对非热窗口的连接变化，再分析可比热强度与持续时间下的抵抗/恢复差异，最后加入Tmin等次级解释。研究为观测性事件研究；季节、同步冲击、维护、供电及测量变化仍可能混杂，不因固定效应或事件图就称准实验。

主要报告不同韧性分项的关联，不把所有信息合并为无透明含义的分数。跨国条件响应也不等于国家整体网络质量：参照标准化会消除部分水平差异，条件恢复模型还筛选了已经受损的事件。

### 9.2 同国家匹配与事件曲线

为每个合格Tmax事件，在同一国家优先同一年、起始日±45天及相同星期结构中寻找等长非热伪事件窗口。候选需满足相同连接质量、排除和恢复观察要求；匹配仅使用事件前连接水平/趋势、时间位置和事件前气象状态，不以事后连接结果挑对照。同期露点/降水用于预定模型调整。找不到对照时报告不可估计，不跨国家硬配。

设 \(j\) 为匹配组、\(u\) 为组内窗口、\(D_{ju}\) 表示Tmax热事件、\(k=-7,\ldots,+7\) 为距起始日：

\[
Y_{jut}=\alpha_{ju}+\lambda_{j,k(t)}
+\gamma_{c,\mathrm{UTC\ hour}\times\mathrm{weekday}}
+\delta_{\mathrm{year}\times\mathrm{month}}
+\sum_{k\ne-1}\beta_kD_{ju}1[k(t)=k]+X_{jut}\theta+\epsilon_{jut}.
\]

主曲线为有符号标准化连接 \(r\)，另报缺口 \(g\) 与低于95%的指示。固定效应可估计性在设计矩阵中检查，共线项按预定规则删去，不按结果选择。长事件在+7日仍可能处于冲击期，恢复另按Tmax事件结束对齐。

国家聚类处理国内相关性，wild cluster bootstrap作小样本敏感性；日历块重抽样或可估计的日期共同冲击调整用于检查同日跨国相关，不能认为国家聚类已解决该问题。日尺度汇总检验10分钟伪重复。前导项是诊断，不显著并不能证明没有混杂。

### 9.3 热负荷—韧性关联：先热压力，后次级修饰

核心结果分别为功能保持率、核心峰值/平均缺口、DHRD及缺口持续；不将量纲不同的原始系数直接比较。一个可解释的事件模型为：

\[
Y_{c,e}=\alpha_c+\delta_{\mathrm{year}\times\mathrm{month}}
+f_{\rm heat}(Exposure_{c,e})
+\theta_1Td_{c,e}+\theta_2P_{c,e}+\epsilon_{c,e}.
\]

预定两个互补热设定：

- **A：累计热负荷。** HD与事件跨度用于描述剂量关联；DHRD同时与等长匹配窗比较，并报告单位观察时长缺口。
- **B：强度—持续分解。** 峰值超阈强度与Tmax热日数，必要时低自由度交互；主要结局用每小时平均缺口、功能保持率与核心峰值，原始DHRD/持续小时另报。对这些总量结局作B设定估计时，优先限制无桥接事件以使跨度等于热日数；如保留桥接，则以热日数加非热桥接日数明确调整观察长度，不同时再加两者之和的跨度。禁止只控制热日数却把桥接造成的更长积分解释为更差韧性。

HD＝平均正超阈×热日数，不将这三项同时解释为独立因果效应。低自由度、共同支持及共线性检查先于二维响应面。功能保持比例采用适合比例的规格或线性条件差异并检查边界；非负积分可用log(1+DHRD)，但结果还原为可解释尺度。

纯控制基准B0只用于技术比较；**主模型M1已包含Tmax热设定**。M2在完全相同样本上加入NTRD或一个预定Tmin摘要，M3再加入有限的热负荷×Tmin交互。露点交互与Tmin比较分别预定、控制多重检验，不能轮换变量追求显著。即使M2没有改善，仍完整报告M1的高温韧性结果。

时间阻断可用2022年开发、2023年选择设置、2024–2025年评估，但已有2024年描述性试算已被查看，不能称从未接触的独立检验。正式模型前登记规则与探索性修改。使用事后天气和含未来观测的连接参照，只能评价回顾性解释/回放，不是前瞻预测准确率。

### 9.4 恢复与所有事件的状态分布

按6.6区分所有Tmax事件的保持/受损/恢复状态；条件生存分析仅针对结束时仍低于95%者，以24槽稳定恢复的确认完成时刻为结局。采用Cox或加速失效时间模型，先纳入Tmax热负荷，再次级增加Tmin；检查比例风险、国家相关、事件数和删失原因。

完整72小时未确认、数据边界、中途缺测分别标记。对有信息性缺测，以完整跟踪样本等作敏感性。终点由Tmax决定；持续热夜是可能解释恢复差异的条件，不是把事件继续延长的理由。条件恢复快不能单独证明总体韧性强，因为不同国家进入“结束时仍受损”组的比例可能不同。

### 9.5 可比条件下的地区差异与既有社会数据

国家/地区比较限定在相近Tmax超阈负荷、绝对温度、持续天数、前期连接状态及质量覆盖的共同支持范围。预先设定可支持的热负荷区间后展示条件响应与不确定性；样本太少、没有重叠或模型依赖极强的单元留白。原始DHRD、恢复时间和DLEP不用于不加调整的全球韧性榜单。

预定六项修饰变量：事件前连接稳定性、电力可及性、收入、城市化、互联网使用率、参考暖季中的首次Tmax事件。前五项量纲与年份明确，社会能力解释优先使用事件前可得的滞后值；第六项不自动等于适应学习。交互项控制FDR，报告组间热暴露支持。DLEP只作社会后果权重，与技术韧性分开展示。

### 9.6 次级验证与可用旧气象资料

- 同一共同样本核查AP、BGP、Telescope，不把验证信号缺失填零，不只保留方向一致地区。
- 使用现有可匹配ADM1与像元超阈人口比例，检验国家平均Tmax是否掩盖局地热压力。
- 使用已有2024年1–3月、7月风场，在窗口完整的相同子样本比较加风前后；日均风分量模长不是阵风，全期没有强风控制。
- 旧ERA5-Land的2024年1–4月与7月Tmax/Tmin可用于共同日期、共同国家、同人口基准下的产品/分辨率敏感性。先核日定义与0.1°权重，不拼接成主气温序列，也不称完全独立气象验证。
- 用固定人口加权圆均值经度确定太阳日偏移，同步重算Tmax/Tmin、阈值、暖季和事件边界。大国优先可用ADM1；太阳时不等于民用夜间。已有UTC日降水不能精确重建当地日，只维持UTC控制或在同样本不含降水的模型中比较。

太阳日、ADM1和像元超阈人口比例需要另行读取服务器已有小时资料，并建立对应空间权重/阈值；不能由当前国家—UTC日表精确反推。目前运行的基础脚本只承担UTC国家日Tmax/Tmin/露点聚合，兼容新主线，无需停下或因改题重跑同一基础任务。

### 9.7 解释边界

可表述为“高温冲击附近的观测连接变化”“给定热负荷的条件响应”“较浅缺口／较快恢复”“短参考暖季热压力”。不能据此写“高温造成断网”“最低温证明设备无法散热”“供电中介已识别”“X人实际断网”或“该国整体韧性世界第一”。

社会指标关联不是政策效果，未来模式气候压力不是未来连接损失。观测不到缺口可能表示保持良好，也可能是测量不敏感，须与覆盖和跨信号证据一起解释。

---

## 10. Results：以高温韧性为主线的待检验结构

以下是计划检验的问题，不是已得到的结果，也不声称完成了外部预注册。

1. **高温冲击与观测覆盖。** Tmax强度、持续天数和剂量在何处、何时出现？同时展示绝对最高温、暖季选择稳定性、连接资格与未匹配地区。
2. **连接功能保持与抵抗。** Tmax事件相对等长非热窗口，保持率、有符号信号与核心峰值缺口如何变化？区间和正常波动有多大？
3. **持续与恢复。** 缺口何时出现、持续多久、Tmax事件结束后何时确认恢复？是否存在抵抗较好但恢复较慢等组合？先给全事件状态，再给条件恢复。
4. **可比高温下的韧性差异。** 在共同热暴露和测量支持内，地区及预定社会条件如何修饰响应？不制作无支持的全球总排名。
5. **补充解释与核查。** Tmin、露点、旧气象产品、有限风场、不同信号及ADM1是否改变主判断？最低温不是结果章节的唯一主角。
6. **社会权重与应用。** DHRD与DLEP对应不同信息，如何在历史回放中展示而不混淆？已有CMIP6若质量通过，以独立次级模块展示未来Tmax压力，不接入未来断网预测。

主关联有支持则按证据强度陈述；平均结果接近零但预定差异稳定可突出异质性；阈值、暖季或质量规则一改即反转则突出不确定性。实际无效范围需在看主结果前依正常波动与信号尺度设定。Tmin次级结果不能被事后升级为替代未成立的主问题。

---

## 11. 主文图件设计

- **Figure 1｜Heat pressure and observation coverage.** 研究框架、Tmax参考/分析时间线、强度与持续分布、绝对温度及覆盖；Tmin不再担任主暴露地图。
- **Figure 2｜Maintaining connectivity during heat.** Tmax事件及匹配非热窗口的保持率、信号曲线和核心峰值缺口，跨信号共同样本与区间。
- **Figure 3｜Disruption duration and recovery after heat.** 核心期、后续72小时的分期缺口与DHRD，所有事件状态比例及条件恢复曲线；对齐最后Tmax核心日。
- **Figure 4｜Resilience under comparable heat loads.** 强度—持续响应与共同支持内的地区/社会条件差异，标注每组事件数、覆盖及不确定性。
- **Figure 5｜Modifiers and social weighting.** 次级Tmin/露点信息与主结论稳健性、DHRD与DLEP的不同意义；不要用人口大或DLEP高表示技术韧性差。
- **Figure 6｜HeatSignal historical resilience replay.** 一个或多个已核查案例，从热压力、功能保持到恢复展示证据和准备措施；明确非实时预警。

如果现有CMIP6模块通过审核，可另设补充图“Future heat pressure”，显示模式内Tmax压力，不挤占历史韧性证据。图数随结果收缩，不为凑图制造结论。

---

## 12. Extended Data 与补充图

优先：0.25°权重与边界审计；国家—信号—年覆盖及完整/孤立事件筛选；Tmax阈值和暖季留一稳定性；绝对温度与共同支持；Tmax事件合并示意和Tmin不改变边界的检查；基线稳定性；降水累计日标签；恢复状态与删失；地区/日期块敏感性。

次级：跨信号、ADM1、像元超阈人口比例、太阳日；旧ERA5-Land与ERA5共同月份对比；有限风场配对子样本；Tmin/露点修饰。已有CMIP6独立展示模式内Tmax变化。RIPE重建失败记录如有需要仅作测量局限说明，不当主观测或成功历史回填。

---

## 13. 表格设计

| 表 | 必报内容 |
|---|---|
| Table 1 资料与主热事件样本 | 新旧数据选择、代码匹配、各信号覆盖、Tmax暖季/阈值有效率、事件及窗口筛选 |
| Table 2 高温冲击与抵抗 | Tmax剂量设定与强度—持续设定、保持率/核心缺口、共同样本、效应及区间 |
| Table 3 持续与恢复 | DHRD/单位时长缺口、持续小时、所有事件状态、条件恢复样本及删失原因 |
| Table 4 条件差异与社会权重 | 六项预定修饰、共同支持、FDR、指标年份/缺失；DLEP分开展示 |
| 补表 变量与来源 | Tmax主、Tmin次级；UTC定义、短参考、暖季、人口权重及ERA5/ERA5-Land区别 |
| 补表 次级与稳健性 | Tmin增量、露点、风子样本、旧气象产品、参考年、暖季与绝对阈值 |
| 补表 排除审计 | 主动断网地理范围、气旋、异常目录、缺失、重叠、未匹配和零人口单元 |

表中不把热暴露直接写作韧性，不把文件数写作样本量，也不混用全体事件和结束时受损者的分母。

---

## 14. 稳健性、负对照与偏差

### 14.1 主研究必做

1. Tmax阈值Q90/Q95、连续两/三/六日、参考年逐一剔除；报告事件重叠和效应改变。
2. 冻结最暖三个月、六个月、全年与绝对Tmax>30/35°C；弱季节性国家单独说明暖季不稳。
3. 累计剂量与峰值—持续两种热设定；累计/每小时缺口、事件核心/全窗峰值，避免长度机械关联。
4. 有符号连接、截断缺口、尾随参照和恢复门槛；完整窗口样本及筛选损失。
5. 同国匹配与跨信号共同样本；逐国/区域留一、日期共同冲击和日级汇总。
6. STOP不确定日期与范围、气旋缓冲、同步异常候选和历史事件核查的替代处理。

### 14.2 已有数据支持的次级检验

Tmin与露点修饰、太阳日/ADM1、像元超阈人口比例、旧ERA5-Land温度共同月份以及风场配对子样本。七年剔除目标年的温度参考只作回顾性敏感性，明确包含目标年之后的信息；不用于前瞻预测，也不替换主参考追求显著。

### 14.3 负对照与解释限制

同国同季节非热伪事件、前导项、保持序列相关结构的日期块平移作为安慰剂。阴性安慰剂不能证明因果关系。

关键限制包括四年参考和四年连接观测较短；暖季筛选不代表全年全部热危险；UTC日与当地钟表日不同；固定人口和国家聚合不代表设备热暴露；IODA覆盖非随机；完整/孤立事件选择；恢复条件样本选择；全期风和供电运行资料缺失；社会指标缺失与时滞；三信号共享平台。未发现连接缺口不自动证明没有局地或用户层面的影响，未来气候模拟不代表未来适应能力。

---

## 15. HeatSignal 竞赛原型：高温韧性回放

### 15.1 使用者与场景

应急部门、社区组织与通信运营团队可以用回放讨论：某次高温期间连接信号发生了什么、证据是否充分、哪些准备措施值得检查。产品不替代正式气象预警，也不作运营级故障判断。

### 15.2 当前最小产品

选择一个质量充分的已发生Tmax事件，依次展示最高温强度/持续与阈值、连接功能保持、核心缺口、后续恢复、质量和不确定性；Tmin/露点作为补充解释层，社会加权代理另列。地图区分“高温压力”“韧性响应”“数据质量”和“社会权重”，不混为一个风险总分，标注“事后再分析回放”，覆盖不足显示“数据不足”，不能显示绿色安全。

**不承诺未来72小时风险概率、预报提前量或命中率。** ERA5 是再分析输入；使用已知事件和未来参照进行的演示不是当时可用信息下的预报回测。以后如获得天气预报档案和单独授权，可建立过去信息参照与前瞻评估，但不是本轮条件。

### 15.3 展示等级与行动卡

先区分“数据不足”“未检测到清晰异常”“存在待核查异常”“多项证据一致的历史缺口”；它们是证据等级，不是校准风险概率。行动卡可列备用联系方式、充电/电源检查、离线信息和邻里联系等讨论项，明确未经干预效果验证。

### 15.4 评估标准

评价可追溯性、覆盖透明度、曲线解释准确性、读图可理解性和回放复现性。若后续另行开展用户测试，记录任务完成率与理解误差；当前不声称已经访谈或证明减少中断。

---

## 16. 竞赛与论文交付

**竞赛轨：** 现有数据覆盖说明、一个或多个经核验Tmax事件的功能保持与恢复案例、交互回放/静态演示、证据等级和准备措施讨论卡。即使平均关联不显著，仍可展示测量边界，但不能宣传已验证的预测能力。

**论文轨：** 2022–2025国家—10分钟/事件面板、固定短参考Tmax热指标、完整筛选审计、功能保持/抵抗、持续与恢复、可比热负荷条件差异、稳健性及预定异质性；按实际结果组织图表。ADM1和CMIP6气候附录视现有数据支持程度加入，不阻塞核心。

两条轨共享审计和定义，但不以竞赛叙事要求统计结果显著，也不为论文完整性启动新数据采购或下载。

---

## 17. 实施安排：保留正在运行的通用计算

现有聚合任务同时输出tmax_c、tmin_c和dewpoint_c，变更研究主线不要求停止、重跑或改写原始数据。2026-10-06 15:55 UTC检查时，人口权重、首月试跑与质量门均通过；201801–201809九个月国家—日表完成，余下月份仍后台运行。首月6758行、218个边界单元，其中214个有人口，零人口单元保留缺失。这是运行快照，不是全期计算完成或正式实证结论。

| 阶段 | 工作 | 验收条件 |
|---|---|---|
| A 已完成的启动准备 | 环境/输入核对、0.25°权重、首月试跑与质量门 | 测试、时间单位、质量检查及来源记录已通过 |
| B 正在运行的国家—日聚合 | 顺序处理现有2018–2025 Tmax/Tmin/露点并断点续算 | 96个月各自审计、缺失、输出完整性及哈希确认 |
| C 现有辅助数据与主定义冻结 | 降水UTC归属与聚合；crosswalk、IODA资格；冻结Tmax参考/暖季/事件/排除 | 不依赖新下载，输入角色明确，样本漏斗可追溯 |
| D 主要韧性分析 | Tmax事件—非热匹配、保持/抵抗/持续/恢复、条件比较 | 不混淆热暴露与韧性，检查支持、前趋势、区间和删失 |
| E 次级验证 | Tmin/露点、BGP/Telescope、ADM1、旧温度产品、风配对子样本、社会修饰 | 同样本比较和多重检验，透明报告未通过或不可估计项 |
| F 图文与原型 | 高温韧性主文图表、历史回放和准备措施说明 | 不将次级夜温或未来模式替代主要历史证据 |
| G 条件允许的次级模块 | 已下载CMIP6模式内Tmax压力 | 资料/日历/参考审计通过；不做连接损失外推 |

B完成前可准备轻量质量表与文档，但不在约3.8 GiB内存主机上并行启动多份全球栅格计算。C之后须先确认分析参数，再估计主结果；本次只更新方案并复用已授权的基础计算，不代表后续模型已运行。时间根据现有任务实测速率与数据清洗情况更新，不以补齐旧1455项下载清单或取得受限数据作为前提。

---

## 18. Go / revise / no-go

**Go：** 现有输入可追溯，Tmax阈值/暖季与质量检查通过，有足够热事件、非热对照和跨信号核查，可以估计抵抗、持续与恢复；不以结果显著或Tmin增量成立作为Go标准。

**Revise：** 覆盖仅支持少数地区、短参考/暖季不稳定、共同热暴露不足、当地日或产品差异明显时，缩小样本或结论范围。无法支持国家比较则只报告事件响应；Tmin没有额外信息不改变主研究题目。

**No-go（针对强主张）：** 日期/来源无法可靠确认、主要缺口为测量异常、无共同支持或需要事后挑选才能成立。保留审计和零结果，不把热暴露地图包装成韧性排名，不以重建连接填补主证据。

---

## 19. 论文结构

Abstract：高温韧性问题、Tmax主暴露、真实数据与样本、分项关联及不确定性。  
Introduction：数字连接的高温适应功能与自身韧性；从暴露转向保持、抵抗和恢复。  
Results：Tmax压力与覆盖 → 功能保持及抵抗 → 持续与恢复 → 可比热负荷下的差异 → 次级条件、社会权重与稳健性。  
Discussion：结果支持什么韧性认识，什么未测量；解释限制、适用地区与准备措施讨论。  
Methods：来源与分块权重、Tmax短参考/暖季、事件、连接参照、缺失/排除、匹配、推断和条件恢复。  
Supplement：全部审计、Tmin/露点/ADM1/风与旧产品；通过审核的独立CMIP6气候压力模块。

---

## 20. 提交前的证据核查

本轮优先完成可用数据内部的跨信号核查、参考稳定性、Tmax热负荷与国家/ADM1可比性、重大候选异常复核、围绕Tmax、高温持续与韧性的文献检索更新和代码复现。已有描述性试算与后续正式分析必须区分，所有规则的冻结日期、探索性修改和失败规格保留日志。

运营商故障记录、设备温度、供电数据或用户访谈可能帮助机制验证，但当前没有这些直接证据，也不作为本轮必须取得的交付。若以后拓展，须另行明确访问、伦理和范围；现阶段定位为宏观互联网可达性的观测研究。

---

## 21. 文件组织与运行约定

主数据原位只读，不搬动或复制数百GB原始文件：

- ERA5：/volume1/homes/Judy/GSC2027/era5
- 既有配套资料：/volume1/homes/Judy/GSC2027/HeatSignal/data
- 本版文档及版本归档：/volume1/homes/Judy/GSC2027/HeatSignal
- 新运行采用独立的 run 目录，分别保存 scripts、config、weights、country_daily、audits、logs 和 status；实际路径写入运行清单。

每次启动写入输入路径、大小、时间/哈希、脚本哈希、软件版本和PID；每月输出采用临时文件完成后原子改名。只在输入与配置一致、输出验证通过时跳过已完成月份。失败记录原因并非零退出，禁止静默用旧网格权重或缺失值继续。新任务只生成派生结果，不恢复任何历史下载器。

本地当前文档为 reference/HeatSignal_proposal.md，本次日期版为 reference/HeatSignal_proposal_revised_2026-10-07.md；2026-10-06及更早日期版保留，不覆盖历史证据。正在运行的基础任务仍使用其不可变脚本/配置；后续Tmax阈值与事件脚本须单独版本化，不回写已启动作业的配置。

---

## 22. 风险登记表

| 风险 | 影响 | 处理 |
|---|---|---|
| 把最低温主题替代高温韧性 | 研究问题偏离 | Tmax主事件和负荷；Tmin仅次级修饰 |
| 相对偏热不等于绝对危险温度 | 设备/高温解释过强 | 固定暖季、绝对Tmax分布及30/35°C敏感性，不称损坏阈值 |
| 短参考与暖季选择不稳定 | 事件母集敏感 | 留一参考年、三/六个月与全年，弱季节性国家单列 |
| 以低暴露或低DLEP称高韧性 | 概念与排名失真 | 热输入、响应与社会权重分开，共同支持内比较 |
| IODA覆盖与完整/孤立筛选 | 样本选择 | 资格和排除漏斗、跨信号共同样本，缺失非稳定 |
| 条件恢复样本选择 | 恢复快被误读为整体韧性强 | 同时报告全体事件受损与保持比例 |
| 全期风、运行供电与设备资料缺失 | 残余混杂、机制不明 | 有限子样本与克制解释，电力可及性非停电 |
| 新旧产品网格/日标签不同 | 暴露错位 | 0.25°主源，0.1°独立聚合共同月份，不拼接 |
| STOP范围/结束未知及气旋坐标问题 | 排除错误 | 地理范围与日期审计、规范经度及敏感性 |
| 小内存和全球文件 | 任务中断 | 现有单进程分块、质量门、日志与检查点 |
| 未来参照与事后再分析 | 误称前瞻预警 | 当前仅回放；不承诺72小时预测准确率 |
| CMIP6外推韧性/连接损失 | 未来主张失真 | 只报告模式内Tmax气候压力，不估未来中断人数 |

---

## 23. 本轮成果与后续交付

1. 以高温韧性为主线的proposal及新旧数据选用清单，服务器同步并保留版本。
2. 通用的2018–2025 Tmax/Tmin/露点国家—日表、固定人口权重与审计；当前正在分批生成，不把启动等于完成。
3. Tmax短参考与暖季、强度/持续/热剂量、2022–2025主事件目录；Tmin次级字段明确分开。
4. IODA质量、参照、STOP/气旋/异常核查与匹配窗口；已有降水控制及风场有效子样本。
5. 功能保持率、核心峰值、持续、DHRD/单位时长缺口、恢复状态与确认时间，以及单独的DLEP。
6. 主关联、共同支持内的条件差异、预定次级和稳健性；对应代码、图表及适用范围。
7. 高温韧性历史回放，不交付未经验证的实时预警或全球韧性总排名。
8. 可选的已有CMIP6模式内Tmax压力附录；资料不足则省略，不阻塞历史研究。

Trinocular、新气象下载、运营商故障机制验证及未来连接损失预测不在当前必需交付中。RIPE重建不用于历史IODA回填。原始资料再分发遵守来源许可。

---

## 24. 结论与下一步

本方案围绕**高温韧性**，具体研究数字连接如何在不同强度、不同持续时间的Tmax热冲击下保持功能、出现缺口并恢复。最高温及持续性是主输入，抵抗与恢复是主结果；最低温和露点是补充解释，既有人口、社会经济、主动断网、气旋及多信号资料按作用选择使用。

现在已有资料足以推进这一框架。保留正在计算的Tmax/Tmin/露点通用表；聚合完成并核验后，下一步冻结Tmax阈值和暖季，完成主事件、连接资格与排除清单，再做韧性比较。无需因为从“热夜”调整为“高温韧性”而重下数据或重跑同一基础气象聚合。

---

## 25. 核心参考文献与数据入口

### 高温、基础设施与社会

1. Stone, B. et al. Compound Climate and Infrastructure Events: How Electrical Grid Failure Alters Heat Wave Risk. *Environmental Science & Technology* (2021). [DOI](https://doi.org/10.1021/acs.est.1c01209)
2. Jiang, K. et al. Spatiotemporal assessment of renewable adequacy during diverse extreme weather events in China. *Nature Communications* (2025). [DOI](https://doi.org/10.1038/s41467-025-60264-9)
3. Casselman, J. W. & Karamperidou, C. Efficiency-weighted cooling degree days reveal opposing temperature and humidity effects on energy demand. *Nature Communications* (2026). [DOI](https://doi.org/10.1038/s41467-026-75388-9)
4. Lu, N. et al. Electricity load forecasting under extreme heat and cold waves. *Nature Communications* (2026). [DOI](https://doi.org/10.1038/s41467-026-77014-0)
5. Short-term association between hot nights and mortality: a multicountry analysis in 178 locations. [PubMed](https://pubmed.ncbi.nlm.nih.gov/40882422/)
6. Nonlinear exposure–response associations of daytime, nighttime, and day–night compound heatwaves with mortality amid climate change. *Nature Communications* (2025). [Article](https://www.nature.com/articles/s41467-025-56067-7)

### 互联网与通信韧性

7. Padmanabhan, R. et al. Residential Links Under the Weather. *ACM SIGCOMM* (2019). [PDF](https://www.cs.umd.edu/users/dml/papers/weather_sigcomm19.pdf)
8. Bischof, Z. S. et al. Destination Unreachable: Characterizing Internet Outages and Shutdowns. *ACM SIGCOMM* (2023). [PDF](https://estcarisimo.github.io/assets/pdf/papers/2023-sigcomm-shutdowns.pdf)
9. Global vulnerability assessment of mobile telecommunications infrastructure to climate hazards using crowdsourced open data. *Nature Communications* (2026). [Article](https://www.nature.com/articles/s41467-026-76197-w)
10. ITU. Overview on adaptation to climate change for information and communication technology networks. [Publication](https://www.itu.int/epublications/en/publication/itu-t-l-suppl-49-2022-07-overview-on-adaptation-to-climate-change-for-information-and-communication-technology-networks/en)

### 数据源（以第7节实际使用范围为准）

11. IODA. [Resource hub](https://ioda.inetintel.cc.gatech.edu/resources?tab=repositories)
12. USC/ISI ANT. [Internet Outage Datasets](https://ant.isi.edu/datasets/outage/)
13. COMUNDA. [Requesting Datasets](https://steelisi.github.io/CLASSNET-DOCS/request/)
14. Copernicus. [ERA5-Land hourly](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land)
15. Copernicus. [ERA5-Land daily statistics](https://cds.climate.copernicus.eu/datasets/derived-era5-land-daily-statistics)
16. WorldPop. [Population counts](https://hub.worldpop.org/project/categories?id=3)
17. World Bank. [Individuals using the Internet](https://data.worldbank.org/indicator/IT.NET.USER.ZS)
18. geoBoundaries. [API](https://www.geoboundaries.org/api.html)
19. Access Now. [#KeepItOn STOP](https://www.accessnow.org/campaign/keepiton/)
20. NOAA. [IBTrACS](https://www.ncei.noaa.gov/products/international-best-track-archive)
21. NASA. [NEX-GDDP-CMIP6](https://www.nasa.gov/nasa-earth-exchange-nex/gddp/downscaled-climate-projections-nex-gddp-cmip6/)

### 竞赛

22. Global Sustainability Challenge. [2026–27 Program Guide](https://www.globalsustainabilitychallenge.org/challenge-details/)
23. Global Sustainability Challenge. [2025–26 winners](https://www.globalsustainabilitychallenge.org/spotlight/2025-26-winners/)


### 本次数据口径补充

24. Copernicus. [ERA5 hourly data on single levels](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels?tab=documentation) — 本轮主温度/露点，不与ERA5-Land混称。
25. WMO. [Climatological normals](https://wmo.int/wmo-climatological-normals) — 四年短参考不称标准气候正常值。
26. ECMWF. [ERA5-Land documentation](https://confluence.ecmwf.int/pages/viewpage.action?pageId=501029136) — 已有降水累计与日归属核查。

27. Climdex. [Indices definitions](https://www.climdex.org/learn/indices/) — 区分最高温暖日与最低温暖夜；本项目两日事件及短参考不是标准WSDI。

文献条目沿用前版记录；本次明确核对的是数据产品与时间口径，不声称重新完成全部文献的系统检索。USC/ISI与COMUNDA入口只保留为历史背景，不代表本轮拥有或使用该数据。
