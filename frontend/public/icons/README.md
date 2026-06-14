# Aether 图标素材清单

本目录是 Aether 地图与卡片所用图标的**单一事实源**。两种素材并存：

1. **[Lucide React](https://lucide.dev/)**（npm: `lucide-react`，ISC license，AGPL 兼容）—— 通用类别图标用它，免去绘制
2. **自绘 PNG 像素图标** —— 仅当 Lucide 无合适候选 / 需要 Aether 独有 brand 风格时才绘

第三方图标（CC0 / CC-BY 等其他来源）将来若引入，必须**另开 `vendor/` 子目录** + 在本表"来源"列标明。

---

## ⚠️ 风格统一性提醒

Lucide 是**线性矢量图标**，自绘是**像素风**，两套混用会有视觉冲突。建议分区使用：

| 用途 | 推荐 |
|---|---|
| 地图上的事件 marker（核心视觉） | **自绘像素** —— 保持 Aether brand 风格 |
| 侧栏 / 筛选器 / Legend / 图例文字旁的小图标 | **Lucide** —— 标准、清晰、零成本 |
| 资产卡片背景的 watermark | **自绘像素**（数量少，单独打磨） |

下表的「Lucide 候选」列只是给你**省工选项**：标 `Lucide:Xxx` 表示该位置可以用 Lucide 替代自绘；标 **自绘** 表示 Lucide 无合适候选或风格上必须自绘。

---

## 1. 存储与命名规范

存储路径：`frontend/public/icons/{category}/{name}.png`

| 维度 | 规则 | 示例 |
|---|---|---|
| 大小写 | 全小写 + kebab-case | `rate-hike.png` |
| 词序 | `<category>-<specific>` | `commodity-oil.png` |
| 国旗 | `<iso2-lowercase>.png` | `us.png` / `cn.png` |
| 多变体 | `@<modifier>` 后缀 | `war@small.png` |
| 格式 | PNG-8（像素风优先） | `rate-hike.png` |

**绘制规格**：64×64 px 源画布；像素对齐 + 关 anti-aliasing；PNG-8 + 透明通道；固定 16-24 色 palette。

Lucide 调用示例：
```tsx
import { Landmark, Coins, Anchor } from 'lucide-react';
<Landmark size={20} strokeWidth={1.5} />
```

---

## 2. 待绘清单（含 Lucide 候选）

> 优先级：**P0** = MVP 必备 / **P1** = 第二批 / **P2** = 长尾
> 状态：☐ 未绘 / ✅ 已绘 / 🟢 Lucide（无需绘）

### 2.1 事件类（`event/`）

| 文件 | 含义 | Lucide 候选 | 优先级 | 状态 |
|---|---|---|---|---|
| event/rate-hike.png | 央行加息 | `TrendingUp` | P0 | ☐ |
| event/rate-cut.png | 央行降息 | `TrendingDown` | P0 | ☐ |
| event/rate-hold.png | 按兵不动 | `Equal` / `Minus` | P0 | ☐ |
| event/hawkish.png | 鹰派表态 | `ChevronsUp` | P0 | ☐ |
| event/dovish.png | 鸽派表态 | `Feather` / `Bird` | P0 | ☐ |
| event/cpi.png | CPI 通胀数据 | `Receipt` / `ShoppingBag` | P0 | ☐ |
| event/jobs.png | 非农 / 就业数据 | `Briefcase` / `Users` | P0 | ☐ |
| event/gdp.png | GDP 数据 | `ChartLine` / `BarChart3` | P0 | ☐ |
| event/war.png | 战争 / 武装冲突 | `Swords` | P0 | ☐ |
| event/oil-shock.png | 油价冲击 | `Fuel` / `Droplets` | P0 | ☐ |
| event/sanctions.png | 制裁 | `Ban` / `ShieldBan` | P0 | ☐ |
| event/tariff.png | 关税 / 贸易战 | `PackageX` | P0 | ☐ |
| event/earnings-beat.png | 财报超预期 | `BadgeCheck` | P0 | ☐ |
| event/earnings-miss.png | 财报不及预期 | `BadgeX` | P0 | ☐ |
| event/bankruptcy.png | 暴雷 / 破产 | `Skull` | P0 | ☐ |
| event/pmi.png | PMI 数据 | `Factory` / `Gauge` | P1 | ☐ |
| event/retail-sales.png | 零售数据 | `ShoppingCart` | P1 | ☐ |
| event/fiscal-stimulus.png | 财政刺激 | `HandCoins` / `Banknote` | P1 | ☐ |
| event/currency-intervention.png | 汇率干预 | `ArrowRightLeft` | P1 | ☐ |
| event/election.png | 选举 | `Vote` | P1 | ☐ |
| event/peace-deal.png | 停火 / 和谈 | `Handshake` | P1 | ☐ |
| event/shipping-disruption.png | 海运通道阻断 | `Ship` / `Anchor` | P1 | ☐ |
| event/opec-cut.png | OPEC+ 减产 | `Fuel` + `Minus` | P1 | ☐ |
| event/opec-raise.png | OPEC+ 增产 | `Fuel` + `Plus` | P1 | ☐ |
| event/supply-chain-break.png | 供应链断裂 | `Unplug` / `Link2Off` | P1 | ☐ |
| event/chip-shortage.png | 芯片短缺 | `Cpu` / `MemoryStick` | P1 | ☐ |
| event/regulation.png | 行业监管 | `Gavel` / `Scale` | P1 | ☐ |
| event/merger.png | 并购 | `Combine` / `Merge` | P1 | ☐ |
| event/downgrade.png | 评级下调 | `ChevronsDown` | P1 | ☐ |
| event/upgrade.png | 评级上调 | `ChevronsUp` | P1 | ☐ |
| event/earthquake.png | 地震 | **自绘** | P1 | ☐ |
| event/hurricane.png | 飓风 | `Tornado` / `Wind` | P1 | ☐ |
| event/flood.png | 洪水 | `Waves` / `Droplets` | P1 | ☐ |
| event/wildfire.png | 山火 | `Flame` | P1 | ☐ |
| event/pandemic.png | 疫情 | `Syringe` / `Bug` | P1 | ☐ |
| event/flash-crash.png | 市场闪崩 | **自绘**（差异化） | P1 | ☐ |
| event/liquidation-cascade.png | 加密清算级联 | **自绘** | P1 | ☐ |
| event/stablecoin-depeg.png | 稳定币脱锚 | `Unlink` | P1 | ☐ |
| event/exchange-hack.png | 交易所被黑 | `KeyRound` / `ShieldOff` | P1 | ☐ |
| event/cyberattack.png | 网络攻击 | `Bug` / `ShieldAlert` | P1 | ☐ |
| event/coup.png | 政变 | **自绘** | P2 | ☐ |
| event/terror.png | 恐袭 | `Bomb` / `AlertTriangle` | P2 | ☐ |
| event/diplomatic.png | 外交事件 | `Flag` / `Handshake` | P2 | ☐ |
| event/sovereign-default.png | 主权违约 | `FileX` / `BadgeAlert` | P2 | ☐ |
| event/drought.png | 干旱 | `SunDim` | P2 | ☐ |
| event/volcano.png | 火山 | **自绘** | P2 | ☐ |
| event/short-squeeze.png | 轧空 | **自绘** | P2 | ☐ |
| event/vol-spike.png | 波动率跳升 | `ChartCandlestick` / `Activity` | P2 | ☐ |
| event/infra-outage.png | 基建故障 | `PowerOff` / `Plug` | P2 | ☐ |
| event/tech-breakthrough.png | 技术突破 | `Sparkles` / `Lightbulb` | P2 | ☐ |

### 2.2 资产大类（`asset/`）

| 文件 | 含义 | Lucide 候选 | 优先级 | 状态 |
|---|---|---|---|---|
| asset/equity.png | 个股通用 | `LineChart` / `CandlestickChart` | P0 | ☐ |
| asset/equity-index.png | 股指 | `BarChart3` | P0 | ☐ |
| asset/bond.png | 国债 / 信用债 | `FileText` / `Receipt` | P0 | ☐ |
| asset/rate.png | 利率 | `Percent` | P0 | ☐ |
| asset/fx.png | 外汇通用 | `ArrowRightLeft` | P0 | ☐ |
| asset/commodity-oil.png | 原油 | `Fuel` / `Droplets` | P0 | ☐ |
| asset/commodity-gold.png | 黄金 | **自绘**（金色质感） | P0 | ☐ |
| asset/commodity-silver.png | 白银 | **自绘**（银色质感） | P0 | ☐ |
| asset/commodity-copper.png | 铜 | **自绘**（铜色质感） | P0 | ☐ |
| asset/commodity-gas.png | 天然气 | `Flame` | P1 | ☐ |
| asset/commodity-agri.png | 农产品 | `Wheat` / `Sprout` | P1 | ☐ |
| asset/commodity-platinum.png | 铂金 / 钯金 | **自绘** | P2 | ☐ |
| asset/etf.png | ETF 通用 | `Layers` / `Boxes` | P1 | ☐ |
| asset/crypto-btc.png | 比特币 | `Bitcoin` ✅ | P0 | ☐ |
| asset/crypto-eth.png | 以太坊 | **自绘**（菱形 ETH logo） | P0 | ☐ |
| asset/crypto-alt.png | 其他主流币 | `Coins` / `CircleDollarSign` | P0 | ☐ |
| asset/crypto-stable.png | 稳定币 | `BadgeDollarSign` | P0 | ☐ |
| asset/crypto-meme.png | Meme 币 | **自绘**（梗图风） | P1 | ☐ |

### 2.3 行业板块（`sector/`）—— Lucide 覆盖率最高

| 文件 | 含义 | Lucide 候选 | 优先级 | 状态 |
|---|---|---|---|---|
| sector/tech.png | 科技 / XLK | `Cpu` | P0 | ☐ |
| sector/semis.png | 半导体 | `MemoryStick` / `Cpu` | P0 | ☐ |
| sector/financial.png | 金融 / XLF | `Banknote` / `Landmark` | P0 | ☐ |
| sector/banks.png | 银行 | `Landmark` / `Building` | P0 | ☐ |
| sector/energy.png | 能源 / XLE | `Zap` / `Fuel` | P0 | ☐ |
| sector/healthcare.png | 医疗 / XLV | `HeartPulse` / `Stethoscope` | P0 | ☐ |
| sector/consumer-staples.png | 必需消费 | `ShoppingBag` | P1 | ☐ |
| sector/consumer-discretionary.png | 可选消费 | `ShoppingCart` / `Gift` | P1 | ☐ |
| sector/industrial.png | 工业 | `Factory` | P1 | ☐ |
| sector/materials.png | 材料 | `Pickaxe` / `Boxes` | P1 | ☐ |
| sector/utilities.png | 公用事业 | `Plug` / `Zap` | P1 | ☐ |
| sector/real-estate.png | 房地产 / REIT | `Home` / `Building2` | P1 | ☐ |
| sector/pharma.png | 制药 | `Pill` / `FlaskConical` | P1 | ☐ |
| sector/insurance.png | 保险 | `Shield` / `Umbrella` | P1 | ☐ |
| sector/airlines.png | 航空 | `Plane` | P2 | ☐ |
| sector/auto.png | 汽车 | `Car` | P2 | ☐ |
| sector/defense.png | 国防军工 | `ShieldHalf` | P2 | ☐ |

### 2.4 央行（`central-bank/`）—— 全部自绘（brand 不可替代）

> 每家央行的 logo 都是独家 brand 标识（Fed 鹰、ECB 星环、PBoC 红章），Lucide 的通用 `Landmark` 无法区分。

| 文件 | 含义 | Lucide 候选 | 优先级 | 状态 |
|---|---|---|---|---|
| central-bank/fed.png | 美联储 Fed | **自绘** | P0 | ☐ |
| central-bank/ecb.png | 欧洲央行 ECB | **自绘** | P0 | ☐ |
| central-bank/boj.png | 日本央行 BoJ | **自绘** | P0 | ☐ |
| central-bank/boe.png | 英国央行 BoE | **自绘** | P0 | ☐ |
| central-bank/pboc.png | 中国央行 PBoC | **自绘** | P0 | ☐ |
| central-bank/snb.png | 瑞士央行 SNB | **自绘** | P1 | ☐ |
| central-bank/rba.png | 澳洲联储 RBA | **自绘** | P1 | ☐ |
| central-bank/boc.png | 加拿大央行 BoC | **自绘** | P1 | ☐ |
| central-bank/rbi.png | 印度央行 RBI | **自绘** | P1 | ☐ |

### 2.5 经济区块（`region/`）—— 全部自绘（brand 徽章）

| 文件 | 含义 | Lucide 候选 | 优先级 | 状态 |
|---|---|---|---|---|
| region/eurozone.png | 欧元区 | **自绘** | P0 | ☐ |
| region/g7.png | G7 | **自绘** | P0 | ☐ |
| region/g20.png | G20 | **自绘** | P0 | ☐ |
| region/opec-plus.png | OPEC+ | **自绘** | P0 | ☐ |
| region/brics.png | BRICS | **自绘** | P0 | ☐ |
| region/asean.png | ASEAN | **自绘** | P0 | ☐ |

### 2.6 国旗（`flag/`）—— Lucide 无国旗，全部自绘 / 或后接 Twemoji

> 替代方案：引入 [Twemoji](https://github.com/twitter/twemoji) flag SVG（CC-BY 4.0，AGPL 兼容），可省去自绘。

| 文件 | 含义 | 优先级 | 状态 |
|---|---|---|---|
| flag/us.png | 美国 | P0 | ☐ |
| flag/cn.png | 中国 | P0 | ☐ |
| flag/jp.png | 日本 | P0 | ☐ |
| flag/gb.png | 英国 | P0 | ☐ |
| flag/de.png | 德国 | P0 | ☐ |
| flag/fr.png | 法国 | P0 | ☐ |
| flag/hk.png | 香港 | P0 | ☐ |
| flag/tw.png | 台湾（地区） | P0 | ☐ |
| flag/ru.png | 俄罗斯 | P0 | ☐ |
| flag/sa.png | 沙特 | P0 | ☐ |
| flag/eu.png | 欧盟旗 | P1 | ☐ |
| flag/ca.png | 加拿大 | P1 | ☐ |
| flag/au.png | 澳大利亚 | P1 | ☐ |
| flag/ch.png | 瑞士 | P1 | ☐ |
| flag/kr.png | 韩国 | P1 | ☐ |
| flag/in.png | 印度 | P1 | ☐ |
| flag/br.png | 巴西 | P1 | ☐ |
| flag/mx.png | 墨西哥 | P1 | ☐ |
| flag/sg.png | 新加坡 | P1 | ☐ |
| flag/ae.png | 阿联酋 | P1 | ☐ |
| flag/tr.png | 土耳其 | P2 | ☐ |
| flag/ir.png | 伊朗 | P2 | ☐ |
| flag/za.png | 南非 | P2 | ☐ |
| flag/id.png | 印尼 | P2 | ☐ |
| flag/my.png | 马来西亚 | P2 | ☐ |
| flag/th.png | 泰国 | P2 | ☐ |
| flag/vn.png | 越南 | P2 | ☐ |
| flag/ph.png | 菲律宾 | P2 | ☐ |
| flag/it.png | 意大利 | P2 | ☐ |
| flag/es.png | 西班牙 | P2 | ☐ |

---

## 3. 已绘 metadata（绘制完一个登记一行）

| 文件 | 作者 | 创作日期 | License | 备注 |
|---|---|---|---|---|
| _（绘完登记）_ |  |  |  |  |

---

## 4. 工作量盘点（启用 Lucide 后）

| 子目录 | 全自绘原本数 | **可用 Lucide** | **必须自绘** |
|---|---|---|---|
| event | 50 | ~42 | ~8 |
| asset | 18 | ~11 | ~7 |
| sector | 17 | 17 | 0 |
| central-bank | 9 | 0 | 9 |
| region | 6 | 0 | 6 |
| flag | 30 | 0 | 30（或换 Twemoji） |
| **合计** | **130** | **~70** | **~60**（其中 30 是国旗，换 Twemoji 后剩 ~30） |

**结论**：若 Lucide + Twemoji 全用上，**真正必须自绘的只剩 ~30 个**（主要是央行 logo + region 徽章 + 几个 Aether 独有事件 + 商品质感色）。从 127 降到 30。

---

## 5. 下一步建议绘制顺序（30 个核心自绘）

1. **9 个央行 logo**（P0 5 个先）：fed, ecb, boj, boe, pboc
2. **6 个 region 徽章**：eurozone, g7, g20, opec-plus, brics, asean
3. **3 个金属商品**：gold, silver, copper
4. **2 个加密特色**：eth（菱形）, crypto-meme
5. **几个 Aether 独有事件**：earthquake, flash-crash, liquidation-cascade, volcano, coup, short-squeeze（这几个 Lucide 无好候选）

剩下 P1/P2 的事件类逐步补全即可。
