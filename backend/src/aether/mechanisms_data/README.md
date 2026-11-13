# 机制库

把"某类事件如何传导到资产价格"拆成可复用的环节，每个环节一张机制卡，并配上历史案例。
规则引擎（`rules_data/`）回答的是"这条标题对应哪几个资产"；机制库回答的是"为什么、在什么条件下、过多久、谁涨谁跌"。

目录：

- `cards/<id>.yaml`：一张卡一个文件，文件名必须等于卡片 `id`。
- `cases/<主题>.yaml`：历史案例，一个文件里放多个。

加载与校验见 `aether/mechanisms/`，测试见 `tests/test_mechanisms.py`。

## 这些内容现在的可信程度

全部卡片和案例都由语言模型凭知识起草，**起草不等于成立**。每条记录自带来源标记：

| 标记 | 位置 | 含义 |
|---|---|---|
| `review.status` | 卡片 | `draft` 未经人审核，`approved` 已审核通过，`rejected` 已否决 |
| `evidence_tier` | 卡片 | `C` 纯逻辑推导，`B` 至少两个支持案例，`A` 已用行情数据验证 |
| `verification.status` | 案例 | `unverified` 仅凭模型记忆，`web_checked` 已对照公开报道核对日期和幅度，`price_verified` 已用自有行情核对，`disputed` 核对后有出入 |
| `recall` | 案例里的每条观察 | 起草时对这条数字的把握：`high` / `medium` / `low` |

加载器强制执行两条规则：`B` 级必须有至少两个 `supports` 案例；`A` 级必须已经人工 `approved`。

当前状态（2026-11-13）：23 张卡全部是 `draft`，其中 19 张 `B` 级、4 张 `C` 级，没有 `A` 级。46 个案例都已 `web_checked`，核对中改正的地方记在各案例的 `verification.notes` 里。还没有任何一条用行情数据验证过。

建议的使用方式：`C` 级只用于提醒，不据此下注；`B` 级小仓位；`A` 级正常仓位。等级随前瞻记录升降。

## 机制卡字段

| 字段 | 说明 |
|---|---|
| `statement` | 一两句话写清因果 |
| `categories` / `shock_nature` | 与 `pipeline/prompts/system_zh.md` 第一步的 7 类事件、5 种冲击性质一一对应 |
| `keywords` | 检索用的提示词 |
| `preconditions` | 适用条件，不满足就不该套用这张卡 |
| `failure_conditions` | 失效条件，出现后应当平仓或放弃 |
| `effects` | 对各个角色的影响，见下 |
| `leads_to` | 常见的下一环，用来把卡片串成链 |
| `cases` | 引用的案例，标明是支持、反对还是两可 |
| `prior` | 主观概率：触发且条件满足时，主要影响方向成立的可能性 |
| `critique` | 对这张卡最有力的反对意见，至少一条 |

`effects` 里每一项：

| 字段 | 说明 |
|---|---|
| `role` | 受影响者的角色，见下表 |
| `target` | 具体指谁，用文字写 |
| `direction` | `up` / `down` / `mixed`；`mixed` 必须在 `condition` 里写明由什么决定方向 |
| `lag` | 时滞。`onset` 首次反应，`peak` 影响最大，`fade` 回吐（省略表示持久）。写法如 `5m-4h`、`3d`、`2w` |
| `crowding` | 市场定价这项影响的速度。`high` 是拼速度的，`low` 是容易被忽略的 |
| `examples` | 示例标的，自由文本，不受资产池限制 |

## 角色词表

同一个事件对不同角色的方向不同，所以卡片按角色而不是按行业名来写。

| 角色 | 含义 |
|---|---|
| `direct_target` | 事件的直接主体 |
| `commodity_price` | 受影响商品或成品的价格 |
| `feedstock_price` | 该环节原料的价格 |
| `producer_in_zone` | 受冲击区域或节点内的生产商 |
| `producer_outside_zone` | 区域外的同类生产商、替代供应方 |
| `downstream_buyer` | 依赖该供给的下游 |
| `upstream_supplier` | 向受冲击方供货的上游 |
| `substitute` | 替代品、替代技术、本土替代者 |
| `freight` | 运价与未受损的承运方 |
| `insurer` | 保险与再保险 |
| `reconstruction` | 重建受益方 |
| `sector_peer` | 同业、同类资产 |
| `counterparty` | 债权方、交易对手、关联方 |
| `leveraged_proxy` | 杠杆化的代理标的 |
| `local_currency` / `local_equities` | 当事国的货币、股指 |
| `rates` | 国债收益率，`up` 表示收益率上行 |
| `usd` | 美元，或加征方的货币 |
| `safe_haven` | 避险资产 |
| `volatility` | 隐含波动率 |
| `long_duration_equity` | 高估值、长久期的股票 |
| `risk_assets` | 广义风险资产 |
| `crypto_majors` / `crypto_alts` / `stablecoin` | 主流币、山寨币、稳定币 |

新增角色要改 `aether/mechanisms/schema.py`，这是有意设的门槛，词表要保持小。

## 链条与概率相乘

一个完整的故事是若干张卡串起来的链，整条链的把握是各卡 `prior` 的乘积：

```python
from aether.mechanisms import load_library

lib = load_library()
for chain in lib.chains("seismic_tsunami_coastal_damage", max_hops=2):
    print(round(chain.joint_prior, 2), " -> ".join(chain.card_ids))
```

三张卡各自有六七成把握，连起来只有约三成。故事讲得通顺不代表它成立。

## 审核一张卡

1. 读 `statement`、`preconditions`、`failure_conditions`，判断逻辑是否成立。
2. 读 `critique`，看反对意见是否足以否决。
3. 看 `cases` 里引用的案例及其 `verification.status`。
4. 修改内容后，把 `review.status` 改成 `approved` 或 `rejected`，填上 `reviewed_by` 和 `notes`。

## 新增一张卡

1. 先在 `cases/` 里补上至少一个案例，凭记忆写的数字标 `recall` 并保持 `unverified`。
2. 在 `cards/` 里新建 `<id>.yaml`，至少写一条 `critique`。
3. 运行 `uv run pytest tests/test_mechanisms.py`。测试会检查引用是否悬空、案例是否都被引用。
