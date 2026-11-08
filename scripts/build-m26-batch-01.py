from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.generation import _word_count  # noqa: E402
from backend.app.readability import flesch_reading_ease  # noqa: E402


OUTPUT = ROOT / "qa" / "question-banks" / "20261109_500-batch-01.json"


def question(
    number: int,
    stem: str,
    options: list[str],
    answer: str,
    explanation: str,
    knowledge_points: list[str],
    grammar_tags: list[str],
    book_source: str,
    difficulty: int,
    **extra,
) -> dict:
    value = {
        "number": number,
        "stem": stem,
        "options": options,
        "answer": answer,
        "explanation": explanation,
        "knowledge_points": knowledge_points,
        "grammar_tags": grammar_tags,
        "book_source": book_source,
        "difficulty": difficulty,
    }
    value.update(extra)
    return value


def passage(
    passage_type: str,
    passage_group_id: str,
    topic: str,
    book_source: str,
    difficulty: int,
    text: str,
    questions: list[dict],
    **extra,
) -> dict:
    value = {
        "validation_profile": "m26",
        "type": passage_type,
        "passage_group_id": passage_group_id,
        "topic": topic,
        "book_source": book_source,
        "difficulty": difficulty,
        "word_count": _word_count(text),
        "passage": text,
        "questions": questions,
        "generation_observations": {},
    }
    if passage_type in {"cloze", "reading"}:
        value["flesch_reading_ease"] = round(flesch_reading_ease(text), 2)
    value.update(extra)
    return value


cloze_media_text = """When a dramatic video about a local restaurant spread through our school chat groups, few students stopped to ask who had produced it or why it had been shared. The video seemed convincing, yet it had been (1) ______ changed to hide the moment when the owner explained the mistake. Before sharing such material, readers should (2) ______ the original source, compare it with an independent report, and ask whether a single detail has been used to make the larger (3) ______ seem more certain than it really is. Our news club invited a journalist to explain how titles may (4) ______ attention by making doubt sound like confidence, and she showed us a photo whose (5) ______ had been cut from the picture. The most (6) ______ report, she argued, is not one that hides doubt but one that states clearly what remains open, separates evidence from opinion, and tells readers when an important question still has no answer. Students who (7) ______ before sharing a claim again give themselves time to notice missing evidence, strong emotion and strange timing. It is also important to (8) ______ a false story openly when new evidence appears rather than defend an earlier post out of pride. In a crowded online (9) ______, speed can create confidence without understanding, and confidence then travels faster than facts. The club therefore suggested a simple (10) ______: no one may forward a serious claim until two independent sources have been checked. At first some students found the (11) ______ difficult, but they soon discovered that a brief delay improved conversation. After several weeks, the group became more (12) ______ about the material it shared and less eager to judge people by a single photo. Their experience suggests that careful judgment is not a single lesson but a habit built through repeated (13) ______ and honest conversation. When students accept that responsibility, a confusing feed becomes an (14) ______ to think rather than a reason to panic. The club now ends every meeting with one question: what evidence would change our (15) ______?"""

cloze_media_questions = [
    question(
        1,
        "选择第 1 空最合适的选项。",
        ["deliberately", "accidentally", "gradually", "generously"],
        "deliberately",
        "视频被剪辑的目的是隐藏店主解释错误的片段，因此 deliberately 表示“故意地”，与 hide 的目的完全一致。accidentally 表示无意中，和有意隐藏相矛盾；generously 表示慷慨地，无法修饰这种剪辑行为。本题还排除了 gradually，因为 gradual 强调过程缓慢，而剪辑行为在这里有明确意图。",
        ["副词：行为意图辨析"],
        ["noun_clauses"],
        "选必二 U1",
        3,
    ),
    question(
        2,
        "选择第 2 空最合适的选项。",
        ["confirm", "verify", "announce", "replace"],
        "verify",
        "verify the original source 表示核查材料的最初来源，是媒体素养中的固定表达。confirm 更常表示确认某个事实或说法，不能直接替代对 source 的核查动作；announce 表示公开宣布，replace 表示替换，二者都与来源核查无关。上下文要求读者在转发前采取核实动作，因此 verify 最准确。",
        ["动词：信息来源核验"],
        ["cleft_basic"],
        "选必一 U1",
        3,
        near_synonym_calibration=True,
        context_clue="the original source 与 independent report 共同指向核查来源",
        clue_argument="verify 能直接接 source，表示核实来源；confirm 通常接事实或说法。",
    ),
    question(
        3,
        "选择第 3 空最合适的选项。",
        ["account", "costume", "melody", "journey"],
        "account",
        "a larger account 表示对事件更完整、更宏大的叙述，与 single detail 形成“细节和整体叙事”的对照。costume 是服装，melody 是旋律，journey 是旅程，三者都不能与 make the larger ... seem more certain 构成自然搭配。这里讨论的是信息如何被包装成完整故事，因此 account 最合适。",
        ["名词：信息叙事与整体表述"],
        ["articles"],
        "必修1 U1",
        3,
    ),
    question(
        4,
        "选择第 4 空最合适的选项。",
        ["attract", "collect", "protect", "divide"],
        "attract",
        "headlines attract attention 是自然搭配，表示标题通过制造确定性来吸引注意。collect attention 不是常用搭配；protect attention 和 divide attention 也不符合“标题吸引读者”的语境。句子强调媒体如何抓住注意力，因此 attract 最准确。",
        ["动词：注意力与媒体标题"],
        ["noun_clauses"],
        "选必二 U2",
        3,
    ),
    question(
        5,
        "选择第 5 空最合适的选项。",
        ["background", "furniture", "audience", "schedule"],
        "background",
        "照片的 background 被裁掉后，画面的含义随之改变，这与后文 changing what viewers believed 形成直接因果。furniture、audience 和 schedule 都无法被“从照片中裁掉”并产生这种语境效果。此处强调的是视觉信息被选择性删除，因此 background 正确。",
        ["名词：图片信息与语境"],
        ["adverbial_clauses"],
        "必修2 U3",
        3,
    ),
    question(
        6,
        "选择第 6 空最合适的选项。",
        ["reliable", "expensive", "familiar", "colourful"],
        "reliable",
        "可靠的报道不会隐藏不确定性，而会清楚说明哪些问题仍无答案，因此 reliable 与后文定义一致。expensive、familiar 和 colourful 描述的是价格、熟悉度或颜色，都不能体现报道在证据上的可信度。该句讨论的是真假与证据，不应选外观或成本形容词。",
        ["形容词：报道可信度"],
        ["prepositions"],
        "必修1 U2",
        3,
    ),
    question(
        7,
        "选择第 7 空最合适的选项。",
        ["pause", "compete", "escape", "complain"],
        "pause",
        "pause before reposting 表示转发前先停一下，为检查证据留出时间，与后文的 notice missing evidence 相符。compete 表示竞争，escape 表示逃离，complain 表示抱怨，都不能表达“延迟转发以核查”的动作。本题通过 before 和 give themselves time 明确提示暂停。",
        ["动词：延迟转发与审慎判断"],
        ["relative_clauses_non_defining"],
        "选必一 U2",
        3,
    ),
    question(
        8,
        "选择第 8 空最合适的选项。",
        ["correct", "repeat", "decorate", "celebrate"],
        "correct",
        "当新证据出现时，应公开 correct a false story，也就是纠正此前的不实说法。repeat 会让错误继续传播；decorate 和 celebrate 与错误信息更无逻辑关系。rather than defend an earlier post 进一步说明这里需要承认并修正错误，因此选 correct。",
        ["动词：纠错与信息责任"],
        ["word_formation"],
        "跨册综合",
        4,
    ),
    question(
        9,
        "选择第 9 空最合适的选项。",
        ["environment", "instrument", "ceremony", "appetite"],
        "environment",
        "a crowded online environment 表示拥挤的网络环境，是描述数字传播空间的自然搭配。instrument、ceremony 和 appetite 分别指工具、仪式和食欲，无法表示信息传播所处的环境。后文 speed 与 confidence travel faster 也明确指向网络传播空间。",
        ["名词：网络传播环境"],
        ["v_ing_nonfinite"],
        "跨册综合",
        4,
        near_synonym_calibration=True,
        context_clue="crowded 与 online 共同限定传播空间",
        clue_argument="environment 可以表示数字空间；instrument 表示工具，不表示传播场域。",
    ),
    question(
        10,
        "选择第 10 空最合适的选项。",
        ["rule", "painting", "ticket", "weather"],
        "rule",
        "冒号后的 no one may forward ... 是对一条规则的完整说明，因此 a simple rule 是最准确的概括。painting、ticket 和 weather 都无法由后面的行为要求来解释。冒号结构提供了直接线索，说明空前需要一个表示规定的名词。",
        ["名词：规则与行为约束"],
        ["passive_voice_tenses"],
        "选必二 U3",
        4,
    ),
    question(
        11,
        "选择第 11 空最合适的选项。",
        ["requirement", "celebration", "invitation", "accident"],
        "requirement",
        "前文要求等待两个独立来源核实后才能转发，这形成了 a requirement，学生起初觉得它 inconvenient 很自然。celebration 和 invitation 都与强制等待的规则无关；accident 表示事故，也不能表示一项要求。代词 the 指回前一句的 rule，因此 requirement 最连贯。",
        ["名词：要求与规则指代"],
        ["relative_clauses_non_defining"],
        "选必一 U1",
        4,
    ),
    question(
        12,
        "选择第 12 空最合适的选项。",
        ["cautious", "generous", "curious", "famous"],
        "cautious",
        "学生更谨慎地对待分享材料，并与 less eager to judge 形成语义呼应，因此 cautious 最合适。generous 表示慷慨，curious 表示好奇，famous 表示著名，都不能体现减少草率判断的变化。about the material it shared 也明确指向对信息保持谨慎。",
        ["形容词：谨慎态度"],
        ["word_formation"],
        "选必二 U3",
        4,
    ),
    question(
        13,
        "选择第 13 空最合适的选项。",
        ["reflection", "competition", "decoration", "silence"],
        "reflection",
        "repeated reflection and honest discussion 表示反复反思和诚实讨论，符合媒体素养需要长期养成的句意。competition 会制造压力而非共同判断；decoration 和 silence 不能表达对信息的思考过程。与 repeated 搭配时，reflection 最能体现习惯形成。",
        ["名词：反思与媒体素养"],
        ["articles"],
        "必修1 U2",
        4,
    ),
    question(
        14,
        "选择第 14 空最合适的选项。",
        ["opportunity", "possibility", "obstacle", "apology"],
        "opportunity",
        "空前是 an，且 opportunity 与 to think 构成“思考的机会”，与后半句 rather than a reason to panic 形成积极转折。possibility 前应使用 a，而且 a possibility to think 不如 opportunity 自然；obstacle 和 apology 更与这里的积极意义冲突。本题同时利用冠词和语义排除干扰项。",
        ["名词：机会与冠词搭配"],
        ["subjunctive_basic_if"],
        "选必二 U2",
        4,
        near_synonym_calibration=True,
        context_clue="an 与 to think 共同限定积极名词",
        clue_argument="an opportunity 是固定自然搭配；possibility 前应为 a。",
    ),
    question(
        15,
        "选择第 15 空最合适的选项。",
        ["belief", "distance", "hunger", "furniture"],
        "belief",
        "what evidence would change our belief 表示什么证据会改变我们的信念，与全文关于核实和修正错误的主旨一致。distance、hunger 和 furniture 都无法作为信息判断讨论中被证据改变的对象。空前 our 与 change 也提示这是可被证据修正的观点。",
        ["名词：信念与证据修正"],
        ["infinitive_nonfinite"],
        "必修1 U1",
        4,
    ),
]

cloze_transport_text = """When our town announced that cars would be (1) ______ from the street beside three schools during morning hours, some shop owners feared that customers would disappear. The town leaders replied that the change was only (2) ______: it would run for six months, gather clear information, and then face a public vote. Its aim was not to punish drivers but to give children safer (3) ______ to school, especially those who walked or cycled through heavy traffic every day. City workers (4) ______ residents, measured air quality, and allowed delivery firms to use the street before eight, while buses received a separate line. Volunteers (5) ______ crossings during the first weeks, helping younger students and reporting dangerous behaviour, and the early results surprised people who had doubted the plan because the number of cars fell (6) ______. A shop that had expected fewer customers reported a (7) ______ rise in sales after families began to spend more time on the quieter street. However, older residents who could not walk far found the new route (8) ______, so the town introduced a free electric bus and improved a parking area for people who could not walk far. What matters in this debate is not whether every driver is pleased but whether the town can (9) ______ security, health, and fair use of public space. Officials promised to publish all traffic counts, accident reports, and shop sales instead of selecting only the figures that looked (10) ______. Researchers will (11) ______ the project until spring and compare it with three nearby towns, while students report their journey times and problems. If the final report shows real gains without serious harm, more families may (12) ______ their usual journeys and choose walking or cycling for short trips. The trial has not removed argument, but it has turned a dispute about cars into a careful talk about how a town can (13) ______ different needs. What began as a local (14) ______ may become a lasting model, while any future (15) ______ will have to protect the routes used by residents nearby."""

cloze_transport_text = cloze_transport_text.replace(
    "a dispute about cars", "an argument about cars"
)

cloze_transport_questions = [
    question(
        1,
        "选择第 1 空最合适的选项。",
        ["restricted", "limited", "invited", "repaired"],
        "restricted",
        "be restricted from the street 表示车辆在特定时段被限制进入该街道，与 beside three schools 和 morning hours 的交通管理语境一致。limited 虽然也表示限制，但常用 limited to，和 from 搭配不自然；invited 表示被邀请，repaired 表示被修理，都无法描述车辆通行规则。介词 from 和公共道路管理语境共同确定 restricted。",
        ["动词：交通限制与介词搭配"],
        ["noun_clauses"],
        "选必二 U1",
        3,
        near_synonym_calibration=True,
        context_clue="from the street 与 morning hours 指向交通限制",
        clue_argument="restricted from 表示被禁止进入；limited 通常搭配 to。",
    ),
    question(
        2,
        "选择第 2 空最合适的选项。",
        ["temporary", "provisional", "ordinary", "familiar"],
        "temporary",
        "后文说明该方案只运行六个月并随后投票，因此 temporary 表示“暂时的”，与固定试行期最吻合。provisional 也接近“临时”，但更强调尚待正式确认的暂行安排；此处核心是时长有限，temporary 更直接。ordinary 和 familiar 分别表示普通和熟悉，与六个月试点的含义无关。",
        ["形容词：暂时方案"],
        ["cleft_basic"],
        "选必一 U1",
        3,
        near_synonym_calibration=True,
        context_clue="run for six months 与 public vote 限定时间性质",
        clue_argument="six-month trial 的核心特征是 temporary；provisional 更偏正式待批准状态。",
    ),
    question(
        3,
        "选择第 3 空最合适的选项。",
        ["paths", "lessons", "uniforms", "opinions"],
        "paths",
        "safer paths to school 表示更安全的上下学路线，与 children who walked or cycled through heavy traffic 对应。lessons、uniforms 和 opinions 与交通安全和通勤路径没有直接关系。to school 前需要表示路线的名词，因此 paths 正确。",
        ["名词：上下学路线"],
        ["articles"],
        "必修1 U1",
        2,
    ),
    question(
        4,
        "选择第 4 空最合适的选项。",
        ["interviewed", "observed", "interrupted", "instructed"],
        "interviewed",
        "City workers interviewed residents 表示工作人员采访居民，与后文他们又测量空气质量和安排送货形成完整的调研过程。observed 表示观察，虽然语法可行，但不如 interviewed 能引出居民意见；interrupted 和 instructed 分别表示打断和指示，语境不符。此处强调的是听取居民看法。",
        ["动词：公众咨询"],
        ["v_ing_nonfinite"],
        "跨册综合",
        3,
    ),
    question(
        5,
        "选择第 5 空最合适的选项。",
        ["monitored", "blocked", "painted", "cleaned"],
        "monitored",
        "volunteers monitored crossings 表示志愿者观察并管理路口，与 helping younger students and reporting dangerous behaviour 的任务相符。blocked 会阻止通行，painted 是刷漆，cleaned 是清洁，都不能涵盖帮助和报告行为。后文的 reporting 明确提示持续观察。",
        ["动词：交通观察与志愿服务"],
        ["passive_voice_tenses"],
        "选必二 U1",
        3,
    ),
    question(
        6,
        "选择第 6 空最合适的选项。",
        ["sharply", "slightly", "briefly", "equally"],
        "sharply",
        "number of cars fell sharply 表示汽车数量大幅下降，与后文结果 surprised people who had doubted the plan 形成呼应。slightly 表示轻微下降，不足以产生强烈惊讶；briefly 描述持续时间，equally 描述相等程度。surprised 和 early results 共同提示下降幅度明显。",
        ["副词：变化幅度"],
        ["adverbial_clauses"],
        "必修1 U2",
        3,
    ),
    question(
        7,
        "选择第 7 空最合适的选项。",
        ["modest", "sudden", "silent", "annual"],
        "modest",
        "a modest rise in sales 表示销售额小幅上升，与商店原本 expected fewer customers 形成温和反差。sudden 强调突然，而句中没有任何突发时间线索；silent 和 annual 分别表示无声和年度，不能修饰 sales rise 的幅度。modest 与 rise 搭配自然。",
        ["形容词：数据变化幅度"],
        ["word_formation"],
        "跨册综合",
        3,
    ),
    question(
        8,
        "选择第 8 空最合适的选项。",
        ["inconvenient", "invisible", "impolite", "incomplete"],
        "inconvenient",
        "older residents who could not walk far 会认为新路线不方便，因此 inconvenient 与 could not walk far 直接对应。invisible、impolite 和 incomplete 分别表示不可见、不礼貌和不完整，都不能描述因行动距离增加产生的不便。后半句提供免费电动公交，也说明问题是不便。",
        ["形容词：无障碍与便利性"],
        ["relative_clauses_defining"],
        "必修1 U3",
        3,
    ),
    question(
        9,
        "选择第 9 空最合适的选项。",
        ["balance", "enlarge", "exchange", "protect"],
        "balance",
        "balance security, health, and fair use 表示在安全、健康和公共空间公平使用之间取得平衡，正对应不同群体利益的冲突。enlarge 表示扩大，exchange 表示交换，protected 虽然积极但不能同时处理三项需求。三项并列和目标之间的冲突提示需要 balance。",
        ["动词：公共利益平衡"],
        ["noun_clauses"],
        "选必二 U2",
        4,
    ),
    question(
        10,
        "选择第 10 空最合适的选项。",
        ["favourable", "frequent", "ordinary", "missing"],
        "favourable",
        "figures that looked favourable 表示只挑选看起来有利的数据，与前文 publish all traffic counts 相对。frequent、ordinary 和 missing 都不能体现“选择性展示有利结果”的意思。instead of selecting only 明确指向原始数据可能带有偏向。",
        ["形容词：数据偏差"],
        ["comparatives_superlatives"],
        "必修2 U1",
        4,
    ),
    question(
        11,
        "选择第 11 空最合适的选项。",
        ["follow", "forbid", "forget", "forgive"],
        "follow",
        "follow the project until spring 表示持续跟踪项目进展，并与 compare it with three nearby towns 形成研究过程。forbid 表示禁止，forget 表示忘记，forgive 表示原谅，都不能表示长期观察。until spring 和 compare 是持续跟踪研究的直接线索。",
        ["动词：跟踪研究"],
        ["tense_system"],
        "选必一 U1",
        4,
    ),
    question(
        12,
        "选择第 12 空最合适的选项。",
        ["adjust", "abandon", "announce", "defend"],
        "adjust",
        "adjust their usual journeys 表示家庭调整日常出行方式，与 choose walking or cycling 的转变相符。abandon 表示完全放弃，语气过强；announce 和 defend 分别表示宣布和辩护，不能与 journeys 形成自然搭配。choose 后列出的新方式说明原有路线需要调整。",
        ["动词：出行方式调整"],
        ["subjunctive_basic_if"],
        "选必二 U2",
        4,
        near_synonym_calibration=True,
        context_clue="choose walking or cycling 表示改变原有方式",
        clue_argument="adjust 可与 journeys 搭配表示调整路线；announce 不能表示改变出行方式。",
    ),
    question(
        13,
        "选择第 13 空最合适的选项。",
        ["satisfy", "repeat", "admire", "replace"],
        "satisfy",
        "satisfy different needs 表示满足不同群体的需要，与前文居民、商店、老人和学生的多种利益对应。repeat 表示重复，admire 表示赞赏，replace 表示替代，都不能表示政策同时回应多种需要。different needs 是 satisfy 的常见搭配。",
        ["动词：满足不同需求"],
        ["word_formation"],
        "选必二 U2",
        4,
    ),
    question(
        14,
        "选择第 14 空最合适的选项。",
        ["experiment", "accident", "concert", "exhibition"],
        "experiment",
        "a local experiment 表示一次地方试点，与 six months、public vote 和 trial 的含义完全一致。accident 表示事故，concert 表示音乐会，exhibition 表示展览，都不能概括交通方案试验。该句总结变化可能成为长期模式，先导性质提示 experiment。",
        ["名词：地方试点"],
        ["relative_clauses_non_defining"],
        "跨册综合",
        4,
    ),
    question(
        15,
        "选择第 15 空最合适的选项。",
        ["expansion", "apology", "entrance", "celebration"],
        "expansion",
        "future expansion 表示未来扩大该试点范围，与 routes used by residents nearby 可能受到影响相呼应。apology、entrance 和 celebration 都不能表示政策规模扩大。while 引出的潜在影响说明这里讨论的是未来扩展。",
        ["名词：项目扩展"],
        ["infinitive_nonfinite"],
        "必修1 U1",
        4,
    ),
]

grammar_trees_text = """① ______ in shallow soil beside a new road, the young trees struggled through their first dry summer. Trees block direct sun from a surface, but they also cool the air through water lost from their leaves, so a green street works like a simple cooling system. Parks create cool islands ② ______ during summer afternoons, while lines of trees protect walkers from the strongest rays. City workers measure ③ ______ at different hours, because a covered side street may remain cooler than a wide road without cover. If the city ④ ______ more trees beside busy crossings, it could reduce heat exposure for people who wait there daily. Only after several summers ⑤ ______ the difference between a newly planted row and a larger tree cover. The trees ⑥ ______ attract birds, reduce traffic noise, and make walking more comfortable. ⑦ ______, they should not be flooded; deep watering once a week is better than a little water daily. Researchers want to know ⑧ ______, so they compare electricity bills from buildings with different levels of cover. By next year, the city ⑨ ______ two hundred more trees and will publish a map of the coolest walking routes. Students now use ⑩ ______ beside the oldest trees, where science lessons connect leaf temperature, soil water, and neighbourhood comfort. The project shows that effective city cooling depends less on the number of trees alone than on careful planting, patient care, and a plan that includes the people who use the street."""

grammar_trees_questions = [
    question(
        1,
        "选择第 ① 空最合适的选项。",
        ["Having been planted", "Being planted", "Having planted", "To be planted"],
        "Having been planted",
        "树已经被种在浅土中，之后才经历第一个干旱夏天，因此需要用完成被动非谓语 Having been planted 表示动作先于主句。Being planted 表示正在被种植；Having planted 的主动关系与 trees 不符；To be planted 表示将来目的，也不能交代先后关系。被动和完成两个意义缺一不可。",
        ["非谓语：完成被动"],
        ["v_ing_nonfinite"],
        "必修1 U2",
        5,
        grammar_category="non_finite_perfect_passive",
    ),
    question(
        2,
        "选择第 ② 空最合适的选项。",
        ["under which people can rest", "for which people can rest", "with which people can rest", "by which people can rest"],
        "under which people can rest",
        "cool islands 是人们在其树荫下休息的场所，介词 under 表示在树荫或遮蔽物之下，因此 under which 与先行词和语义都一致。for which 表示目的，with which 表示工具，by which 表示方式，都不能表达“在阴凉下休息”。本题同时考查介词加关系代词和语义搭配。",
        ["定语从句：介词 + which"],
        ["relative_clauses_non_defining"],
        "选必一 U1",
        4,
        grammar_category="preposition_plus_which",
    ),
    question(
        3,
        "选择第 ③ 空最合适的选项。",
        ["what temperatures the streets reach", "which temperatures the streets reach", "that temperatures the streets reach", "how temperatures the streets reach"],
        "what temperatures the streets reach",
        "measure 后需要名词性从句作宾语，what temperatures 表示“达到什么样的温度”，what 在从句中限定名词 temperatures。which 暗示已有范围，that 不能保留后面的名词中心语，how temperatures 搭配不完整。这里的核心是测量结果的数值范围。",
        ["名词性从句：what 结构"],
        ["noun_clauses"],
        "选必二 U2",
        4,
        grammar_category="what_noun_clause",
    ),
    question(
        4,
        "选择第 ④ 空最合适的选项。",
        ["were to plant", "was to plant", "is to plant", "has been planted"],
        "were to plant",
        "If the city were to plant 是与现在事实相反的虚拟条件句，were to do 表示假设性的未来行动。city 为单数但正式虚拟条件中仍可用 were；was to plant 会破坏统一的虚拟语气，is to plant 和 has been planted 都与 could reduce 的假设结构不匹配。主语 city 与 plant 之间还是主动关系。",
        ["虚拟语气：条件句"],
        ["subjunctive_basic_if"],
        "选必二 U3",
        5,
        grammar_category="subjunctive",
    ),
    question(
        5,
        "选择第 ⑤ 空最合适的选项。",
        ["did residents recognize", "residents recognized", "had residents recognized", "were residents recognized"],
        "did residents recognize",
        "Only after several summers 位于句首时，主句要使用部分倒装，因此助动词 did 放到主语 residents 前。residents recognized 没有倒装；had residents recognized 表示过去完成，与主句时间不符；were residents recognized 变成被动，居民不会“被认出差异”。时间状语 only after 决定了 did 倒装。",
        ["倒装：Only after 部分倒装"],
        ["partial_inversion_basic"],
        "选必二 U3",
        5,
        grammar_category="inversion",
    ),
    question(
        6,
        "选择第 ⑥ 空最合适的选项。",
        ["which line the main road", "which lines the main road", "where line the main road", "whose line the main road"],
        "which line the main road",
        "先行词 trees 是复数，定语从句的谓语要用复数 line，关系词在从句中作主语，因此 which line 正确。which lines 的主谓不一致；where 不能在从句中作主语；whose 表示所属关系，但 line the road 不是“其路线”的结构。主谓一致是本题的关键。",
        ["定语从句：主谓一致"],
        ["relative_clauses_defining"],
        "必修1 U2",
        3,
        grammar_category="relative_clause",
    ),
    question(
        7,
        "选择第 ⑦ 空最合适的选项。",
        ["Although young trees need water", "Because young trees need water", "Unless young trees need water", "If young trees need water"],
        "Although young trees need water",
        "前句承认幼树需要水，后句强调不应淹水，二者构成让步关系，因此 Although 最合适。Because 会变成因果重复；Unless 和 If 都没有体现“需要水但不能过量”的让步对比。分号后的否定建议是选择让步连词的关键线索。",
        ["状语从句：让步关系"],
        ["adverbial_clauses"],
        "必修1 U2",
        3,
        grammar_category="adverbial_clause",
    ),
    question(
        8,
        "选择第 ⑧ 空最合适的选项。",
        ["whether shade lowers electricity use", "what shade lowers electricity use", "that shade lowers electricity use", "which shade lowers electricity use"],
        "whether shade lowers electricity use",
        "want to know 后表示“是否”的不确定问题，需要 whether 引导名词性从句；后文比较不同遮阴程度的电费，说明研究者想知道遮阴是否降低用电。what 和 which 会错误地要求名词中心语，that 则把不确定问题变成已知事实。so they compare 进一步证明结果尚未确定。",
        ["名词性从句：whether"],
        ["noun_clauses"],
        "选必二 U2",
        4,
        grammar_category="noun_clause",
    ),
    question(
        9,
        "选择第 ⑨ 空最合适的选项。",
        ["will have planted", "will plant", "would have planted", "has planted"],
        "will have planted",
        "By next year 表示到将来某时间点之前完成的动作，需要使用将来完成时 will have planted。will plant 只表示将来会发生，不能突出“到明年之前完成”；would have planted 表示过去将来完成，has planted 表示现在已经完成。By next year 是将来完成时的直接标志。",
        ["时态：将来完成时"],
        ["tense_system"],
        "必修2 U1",
        4,
        grammar_category="tense_system",
    ),
    question(
        10,
        "选择第 ⑩ 空最合适的选项。",
        ["an outdoor classroom", "a outdoor classroom", "the outdoor classroom", "outdoor classroom"],
        "an outdoor classroom",
        "outdoor 以元音音素开头，单数可数名词前需要不定冠词 an，表示“一个户外教室”；an outdoor classroom 与前文没有明确指代关系。a outdoor classroom 冠词形式错误，the 会产生不必要的特指，零冠词则缺少单数可数名词所需限定词。冠词和首次提及共同确定 an。",
        ["冠词：不定冠词"],
        ["articles"],
        "必修2 U1",
        2,
        grammar_category="articles",
    ),
]

reading_orchestra_text = """When a community music group began holding open practice sessions in an old railway hall, its members expected only a few curious neighbours. They also thought a handful of families might wait quietly for the players to finish. Instead, people came with children, notebooks, walking sticks, and questions about instruments they had never tried closely before. The group had lost its usual concert audience during a long period of repairs at the town hall. The open sessions were first planned as a short-term answer. They soon became the part of the week that players and residents valued most, because the hall let people listen without needing expert knowledge or costly tickets.

During a normal evening, the conductor explains why a passage is repeated, and a violin player shows how bow pressure changes the sound. Members of the audience are also invited to move closer when the music becomes quiet. These comments do not turn the session into a lecture; rather, they make the unseen choices of a performance visible and give listeners a reason to care about details they might otherwise miss. One older resident said that she had attended concerts for decades but had never realised how much silent counting took place before a group began together.

A teenager who came only to finish a school project returned each week and later joined the youth singing group. This showed that access can lead to taking part when the first step is made easy. The third part of the evening is less formal on purpose: chairs are moved, visitors may ask short questions, and the group tries a new piece in front of everyone. This part matters because it changes the audience from judges of a finished product into witnesses of a process that is not yet fixed. Not every test succeeds, and the players sometimes stop after a few bars, laugh, and begin again; those moments make the art feel human rather than distant.

The town hall has now opened again, but the group has decided to keep the open sessions and make them a lasting part of its season. Its experience suggests that arts groups become stronger when they offer people more than a seat at the end of the work, inviting them instead into the questions, mistakes, and discoveries that give a performance meaning."""

reading_orchestra_text = (
    reading_orchestra_text.replace("practice sessions", "practice evenings")
    .replace("open sessions", "open evenings")
    .replace("the session into a lecture", "the event into a lecture")
    .replace("short-term answer", "brief answer")
    .replace("unseen choices", "small decisions")
)

reading_orchestra_questions = [
    question(
        1,
        "What central idea does the passage develop about cultural events?",
        [
            "Audiences benefit when the creative process is opened to them.",
            "Music groups should replace formal concerts with open evenings.",
            "Community music depends mainly on public funding.",
            "Children learn instruments faster when they watch adults.",
        ],
        "Audiences benefit when the creative process is opened to them.",
        "全文从观众进入排练现场、理解演奏选择，写到参与者逐渐加入，中心在于开放艺术过程带来的价值。第二个选项把“保留开放排练”误读为“取消正式音乐会”；第三个选项夸大了公共资金的作用，第四个选项把个别青少年的经历扩大为普遍学习规律。主旨题需要概括全文变化，而不是抓住单一细节。",
        ["阅读理解：主旨概括"],
        ["noun_clauses"],
        "选必二 U1",
        4,
        reading_type="main_idea",
        evidence_sentence="These comments do not turn the event into a lecture; rather, they make the small decisions of a performance visible and give listeners a reason to care about details they might otherwise miss.",
    ),
    question(
        2,
        "Why did the group decide to keep the open evenings after the town hall opened again?",
        [
            "The format had created a strong connection with the community.",
            "The music group could no longer afford the town hall.",
            "The town council required every concert to be free.",
            "The musicians wanted to avoid performing finished works.",
        ],
        "The format had created a strong connection with the community.",
        "文中说开放排练成为音乐家和居民最珍惜的每周活动，并且后来仍决定保留，说明它建立了稳定的社区联系。第二个选项与 town hall reopened 相反；第三个选项没有提到市议会强制免费，第四个选项也把“开放过程”夸大成了拒绝完整作品。答案必须综合排练价值和保留决定。",
        ["阅读理解：因果推断"],
        ["cleft_basic"],
        "选必一 U1",
        4,
        reading_type="inference",
        evidence_sentence="The town hall has now opened again, but the group has decided to keep the open evenings and make them a lasting part of its season.",
    ),
    question(
        3,
        "What is the author's attitude toward the less formal section of the evening?",
        [
            "It is a purposeful way to make artistic work more accessible.",
            "It is an unfortunate compromise that weakens the music.",
            "It is mainly a marketing trick to sell more tickets.",
            "It is useful only for children who have never seen a music group.",
        ],
        "It is a purposeful way to make artistic work more accessible.",
        "作者用 on purpose 和 it changes the audience ... into witnesses 说明这一环节是有意设计，并让观众接近创作过程。第二个选项与 make the art feel human 的积极评价相反；第三个选项把开放排练误解为销售手段；第四个选项又把适用范围缩得太窄。态度题应结合评价词和功能说明。",
        ["阅读理解：作者态度"],
        ["v_ing_nonfinite"],
        "选必一 U2",
        4,
        reading_type="purpose_or_attitude",
        evidence_sentence="The third part of the evening is less formal on purpose: chairs are moved, visitors may ask short questions, and the group tries a new piece in front of everyone.",
    ),
    question(
        4,
        "What is the main function of the third paragraph?",
        [
            "It gives examples showing how access can lead to deeper involvement.",
            "It explains the history of the railway hall.",
            "It compares ticket prices at different concert halls.",
            "It argues that open evenings should never be recorded.",
        ],
        "It gives examples showing how access can lead to deeper involvement.",
        "第三段用青少年每周返回并加入合唱团的事例，以及观众观察未完成过程的变化，证明开放参与会形成更深联系。铁路大厅历史出现在第一段，票价比较没有出现，录音问题也没有讨论。段落功能题要关注该段对全文论点提供的作用。",
        ["阅读理解：段落作用"],
        ["adverbial_clauses"],
        "必修1 U2",
        4,
        reading_type="paragraph_function",
        evidence_sentence="A teenager who came only to finish a school project returned each week and later joined the youth singing group.",
    ),
]

reading_repair_text = """On the first Saturday of every month, the community centre opens its main room to a repair club where neighbours bring damaged lamps, coats, loose chair legs, and small machines that have stopped working. No money changes hands, and no one is expected to know how to repair anything before arriving. Instead, volunteers sit beside visitors, explain each step, and invite the owner to hold the tool or test the switch.

The aim is not simply to rescue an object but to reduce waste while helping people understand how everyday products are built. Many visitors arrive believing that a small fault means the whole item must be replaced, and the first surprise is often how quickly a loose wire or worn belt can be found. A retired electrical worker who volunteers at the club says that the most useful tool is not a machine but a question: what changed just before the object stopped working? That question turns repair into a form of investigation and helps owners notice details they had ignored.

One student brought a desk lamp that had been left on a shelf for two years, and after replacing a cheap switch she began repairing bike lights for friends. The club also keeps a simple record of failed repairs, because some products are glued shut or use parts that may not be bought separately. These failures are displayed beside successful repairs, not hidden, so visitors can see that not every object can be saved and that design choices affect how long a product lasts. The student and the failed repair shelf show that learning comes from testing, observing, and admitting limits.

Local shops have responded in different ways: some donate spare parts, while others worry that free repairs reduce their income. The organisers reply that the club mainly handles simple faults and often sends complex jobs to professionals, so cooperation can replace doubt. After two years, the group estimates that it has kept more than eight hundred kilograms（千克） of material out of waste. More importantly, visitors leave with a changed habit: they are less likely to throw something away before asking whether it can be understood, opened, and repaired."""

reading_repair_questions = [
    question(
        1,
        "What question does the retired electrical worker consider most useful?",
        [
            "Whether a recent change happened before the failure.",
            "How much a replacement product will cost.",
            "Which shop sells the strongest new machines.",
            "How many visitors arrived that morning.",
        ],
        "Whether a recent change happened before the failure.",
        "电工认为最有用的工具是追问物品停止工作前刚刚发生了什么变化，这与“最近变化导致故障”的表述一致。价格、商店选择和到访人数都不是寻找故障原因的问题。原文用 what changed 强调故障前的变化，因此答案应保留这一因果方向。",
        ["阅读理解：细节定位"],
        ["articles"],
        "必修1 U1",
        3,
        reading_type="detail",
        evidence_sentence="A retired electrical worker who volunteers at the club says that the most useful tool is not a machine but a question: what changed just before the object stopped working?",
    ),
    question(
        2,
        "Why does the repair club display failed repairs next to successful ones?",
        [
            "To show that useful learning includes understanding product limits.",
            "To prove that all modern products are badly designed.",
            "To persuade visitors to buy parts from local shops.",
            "To discourage people from bringing small machines.",
        ],
        "To show that useful learning includes understanding product limits.",
        "展示失败案例是为了让人看到并非所有物品都能修好，并且设计方式会影响产品寿命，因此它强调诚实学习和认识限制。第二个选项把部分设计问题扩大为全部产品；第三个选项与展示失败的目的无直接关系；第四个选项则会违背维修活动的开放精神。并列展示成功与失败说明学习不只来自成功。",
        ["阅读理解：目的推断"],
        ["cleft_basic"],
        "选必一 U1",
        4,
        reading_type="inference",
        evidence_sentence="These failures are displayed beside successful repairs, not hidden, so visitors can see that not every object can be saved and that design choices affect how long a product lasts.",
    ),
    question(
        3,
        "What does the underlined word \"handles\" most nearly mean in the fourth paragraph?",
        [
            "Deals with",
            "Lifts up",
            "Sells quickly",
            "Hides away",
        ],
        "Deals with",
        "handles simple faults 表示处理简单故障，与后文复杂工作被送往专业人员形成“简单问题自行处理”的对应。lifts up 是拿起，sells quickly 是快速出售，hides away 是藏起来，都无法与 faults 构成维修语境。该词指咖啡馆处理问题的范围，而非物理动作。",
        ["阅读理解：语境词义"],
        ["noun_clauses"],
        "选必一 U2",
        4,
        reading_type="vocabulary_in_context",
        evidence_sentence="The organisers reply that the club mainly handles simple faults and often sends complex jobs to professionals, so cooperation can replace doubt.",
    ),
    question(
        4,
        "What is the main function of the third paragraph?",
        [
            "It presents examples that reveal both learning and repair limits.",
            "It explains why the repair club charges no money.",
            "It describes how local shops were established.",
            "It lists the tools needed to repair every machine.",
        ],
        "It presents examples that reveal both learning and repair limits.",
        "第三段先写学生成功修灯并帮助朋友，再写失败维修记录，二者共同说明维修既带来学习，也受到产品设计限制。免费维修原则在第一段，店铺历史和完整工具清单都不是本段中心。段落功能应概括“成功与失败两类例子”的共同作用。",
        ["阅读理解：段落作用"],
        ["relative_clauses_non_defining"],
        "选必一 U1",
        4,
        reading_type="paragraph_function",
        evidence_sentence="The student and the failed repair shelf show that learning comes from testing, observing, and admitting limits.",
    ),
]

gap_family_text = """In many families, practical knowledge passes silently from one generation to the next, yet it is often lost when young people move to cities, live alone, or depend on professional services for every small problem. An older relative may know how to make a knife sharp, repair damaged clothing, or judge when bread has grown, but such skills often remain unnoticed until the person who holds them is no longer nearby. When the older person stops being able to demonstrate a task, the gap may feel like a sudden loss rather than a gradual absence of memory. Digital videos offer useful access to information, and they can show a procedure from several angles, but information alone does not create judgment. (1) ______

A family kitchen or work area can become a place for teaching when adults explain not only what to do but also how to notice when something is going wrong. A young person who cooks with an aunt learns to listen for the change in sound as water begins to boil and to feel when dough has been pressed enough, and those signals are difficult to describe without practice. (2) ______

The process also changes the relationship between generations. Young people are often seen as learners, while older relatives are seen as providers of advice; when they complete a practical task together, both roles become more equal and more flexible. (3) ______

Specific traditions matter as well because they carry memory and identity, not just technique. (4) ______ Teaching can fail when it becomes a test or a performance, so the atmosphere should leave room for mistakes, questions, and repeated attempts. A family that laughs at a badly shaped dumpling is more likely to continue the lesson than one that treats every error as evidence of carelessness. (5) ______

The goal is not to preserve every old method exactly as it was once used. It is to give young people enough practical confidence to solve problems, appreciate the knowledge around them, and pass something useful forward when their own turn comes."""

gap_family_options = {
    "A": "Over time, repeated practice turns a clumsy action into a dependable habit.",
    "B": "As a result, families should avoid all digital instructions and depend only on older relatives.",
    "C": "This shared work also gives family members something to discuss when conversation becomes difficult.",
    "D": "For example, a grandmother may teach a teenager to fold dough while explaining how the family once prepared food with fewer tools.",
    "E": "However, a video cannot replace the confidence gained by working beside someone who can stop and explain a hidden step.",
    "F": "That sense of usefulness can strengthen a young person's place in the family long after the practical task is finished.",
    "G": "Meanwhile, a forgotten skill is always less valuable than a new academic subject.",
}

gap_family_questions = [
    question(
        1,
        "选择最适合第 (1) 空的句子。",
        list(gap_family_options.values()),
        "E",
        "第 1 空承接数字视频“能提供信息但不等于判断力”，需要转折说明视频无法替代身边人的现场指导。E 项的 However 和 cannot replace 正好完成这一转折。B 项把比较扩大为“完全禁止数字材料”，过于绝对；G 项转向学业价值比较，与本段讨论的技能传递不一致。判断依据是 however 后的“视频 vs. 现场指导”对照。",
        ["七选五：转折与信息局限"],
        ["noun_clauses"],
        "选必二 U1",
        4,
        cohesion_type="logical_connector",
    ),
    question(
        2,
        "选择最适合第 (2) 空的句子。",
        list(gap_family_options.values()),
        "A",
        "前文写通过声音、触感等反复练习获得判断，A 项的 Over time, repeated practice 接着说明练习如何把生疏动作变成稳定习惯。B 项否定数字工具，与上文无关；G 项转而贬低旧技能，也无法承接“练习形成判断”。时间推进和 repeated practice 是本题的主要线索。",
        ["七选五：时间推进"],
        ["word_formation"],
        "选必二 U2",
        4,
        cohesion_type="time_order",
    ),
    question(
        3,
        "选择最适合第 (3) 空的句子。",
        list(gap_family_options.values()),
        "C",
        "前句说共同完成实际任务会让长幼角色更平等、更灵活，C 项的 This shared work 指代这一共同劳动，并补充它为家庭提供交流话题。B 项再次走向全面否定数字材料，G 项与代际合作主题无关。代词 This 的回指范围决定了 C 项最连贯。",
        ["七选五：代词指代"],
        ["pronouns"],
        "必修1 U2",
        4,
        cohesion_type="pronoun_reference",
    ),
    question(
        4,
        "选择最适合第 (4) 空的句子。",
        list(gap_family_options.values()),
        "D",
        "空前句说具体传统承载记忆和身份，D 项用 For example 引出祖母教孙辈做面食并讲述家庭过去的具体例子。B 项是错误结论，G 项与家庭传统无关。从一般判断到具体实例，Example 结构非常明确。",
        ["七选五：举例与总分结构"],
        ["conjunctions"],
        "必修1 U3",
        4,
        cohesion_type="general_to_specific",
    ),
    question(
        5,
        "选择最适合第 (5) 空的句子。",
        list(gap_family_options.values()),
        "F",
        "前文强调允许错误和反复尝试，F 项的 usefulness 回指学习实用技能和参与家庭劳动，并说明这种价值会延续到任务结束之后。B 项绝对否定数字资源，G 项否定旧技能，二者都偏离温和、实践性的结论。usefulness 与前文 practical task 形成词汇复现。",
        ["七选五：词汇复现与结论"],
        ["word_formation"],
        "选必二 U2",
        4,
        cohesion_type="lexical_repetition",
    ),
]


passages = [
    passage(
        "cloze",
        "M26-NEW-CLOZE-01",
        "媒体信息",
        "选必二 U1",
        4,
        cloze_media_text,
        cloze_media_questions,
    ),
    passage(
        "cloze",
        "M26-NEW-CLOZE-02",
        "城市交通",
        "选必一 U2",
        4,
        cloze_transport_text,
        cloze_transport_questions,
    ),
    passage(
        "grammar_fill",
        "M26-NEW-GRAMMAR-01",
        "自然科普",
        "必修2 U1",
        4,
        grammar_trees_text,
        grammar_trees_questions,
    ),
    passage(
        "reading",
        "M26-NEW-READING-01",
        "文化艺术",
        "选必二 U1",
        4,
        reading_orchestra_text,
        reading_orchestra_questions,
    ),
    passage(
        "reading",
        "M26-NEW-READING-02",
        "志愿公益",
        "选必一 U1",
        4,
        reading_repair_text,
        reading_repair_questions,
    ),
    passage(
        "gap_fill",
        "M26-NEW-GAP-01",
        "家庭代际",
        "选必二 U2",
        4,
        gap_family_text,
        gap_family_questions,
        options=gap_family_options,
    ),
]

package = {
    "format_version": "bank-v1",
    "name": "20261109_500#batch-01",
    "target_size": sum(len(item["questions"]) for item in passages),
    "difficulty_profile": "standard",
    "generated_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
    "composition": {
        "cloze": 2,
        "grammar_fill": 1,
        "reading": 2,
        "gap_fill": 1,
    },
    "passages": passages,
}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(
    json.dumps(package, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
print(OUTPUT)
