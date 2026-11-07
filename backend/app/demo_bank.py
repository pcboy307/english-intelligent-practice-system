"""Deterministic 30-question half-day demo bank.

This fixture deliberately contains one cloze, one grammar-fill and one gap-fill
passage. It is temporary sprint content, not Bank#1 production content.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

BANK_ID = "00000000-0000-4000-8000-000000000002"
QUESTION_PREFIX = "DEMO2-"


@dataclass(frozen=True)
class DemoQuestion:
    id: str
    bank_id: str
    type: str
    passage_group_id: str
    passage: str
    stem: str
    options: list[str] | None
    answer: str
    explanation: str
    knowledge_points: list[str]
    grammar_tags: list[str]
    book_source: str
    difficulty: int

    @property
    def question_order(self) -> int:
        match = re.search(r"(\d+)$", self.id)
        if not match:
            raise ValueError(f"Question ID has no ordinal: {self.id}")
        size = {
            "cloze": 15,
            "grammar_fill": 10,
            "reading": 4,
            "gap_fill": 5,
        }[self.type]
        return (int(match.group(1)) - 1) % size + 1

    @property
    def passage_order(self) -> int:
        return {"cloze": 1, "grammar_fill": 2, "reading": 3, "gap_fill": 3}[self.type]

    @property
    def blank_label(self) -> str:
        if self.type == "grammar_fill":
            return chr(0x2460 + self.question_order - 1)
        return f"({self.question_order})"

    @property
    def presentation_mode(self) -> str:
        return {
            "cloze": "cloze_single_choice",
            "grammar_fill": "passage_single_choice",
            "reading": "reading_single_choice",
            "gap_fill": "seven_choice",
        }[self.type]

    @property
    def book_bucket(self) -> str:
        if self.book_source.startswith("选必二"):
            return "选必二"
        if self.book_source.startswith("选必一"):
            return "选必一"
        if self.book_source.startswith("选必") or self.book_source == "跨册综合":
            return "cross_book"
        return "必修"

    @property
    def topic(self) -> str:
        return {
            "DEMO-CLOZE-01": "environment",
            "DEMO-CLOZE-02": "transport",
            "DEMO-GRAMMAR-01": "community garden",
            "DEMO-GRAMMAR-02": "school science",
            "DEMO-READING-01": "education",
            "DEMO-READING-02": "technology",
            "DEMO-READING-03": "environment",
            "DEMO-READING-04": "culture",
            "DEMO-READING-05": "health",
            "DEMO-GAP-01": "school life",
            "DEMO-GAP-02": "volunteering",
        }[self.passage_group_id]


CLOZE_TEXT = (
    "Last April, our class joined a beach clean. We met early in "
    "the morning and divided into small (1) so that every area could be checked. "
    "We collected bottles, paper and pieces of (2) from the sand. Everyone worked "
    "(3) because damaged glass could hurt someone. (4) the work was hard, nobody "
    "complained. Our teacher (5) that each group should record what it found. The "
    "result showed that most waste came from food packaging. We made a (6) to "
    "reduce this waste at school. Near noon, we (7) a group of birds beside the "
    "water. We moved away quietly to (8) leave them in peace. Some volunteers had "
    "(9) worked at the beach before, so they knew the safest route. We finished "
    "the task (10) using any plastic bags. The local officer said our (11) was "
    "helpful, and asked us to share the data with the community. We also agreed "
    "that the message should (12) beyond our classroom. A week later, more "
    "families joined the next beach clean. Although the beach looked cleaner, we felt "
    "(13) about the work we had done. Protecting the coast requires steady action, "
    "and every small step is part of a larger (14). We left with a clear sense of "
    "(15)."
)

CLOZE_QA = [
    ("teams", ["groups", "teams", "pieces", "signs"], "team_noun", "subject_verb_agreement"),
    ("plastic", ["plastic", "music", "weather", "silence"], "material_noun", "articles"),
    ("carefully", ["carefully", "loudly", "suddenly", "rarely"], "manner_adverb", "word_formation"),
    ("Although", ["Because", "Although", "Unless", "So"], "concession", "adverbial_clauses"),
    ("suggested", ["suggested", "refused", "forgot", "divided"], "reporting_verb", "subjunctive_basic_should"),
    ("decision", ["decision", "distance", "direction", "difficulty"], "decision_noun", "word_formation"),
    ("noticed", ["noticed", "covered", "borrowed", "replaced"], "observation_verb", "tense_system"),
    ("avoid", ["avoid", "finish", "invite", "prepare"], "verb_pattern", "v_ing_nonfinite"),
    ("already", ["already", "instead", "hardly", "perhaps"], "time_adverb", "articles"),
    ("without", ["without", "against", "between", "during"], "object_preposition", "prepositions"),
    ("effort", ["effort", "habit", "product", "promise"], "effort_noun", "pronouns"),
    ("reach", ["reach", "hide", "divide", "remain"], "purpose_verb", "adverbial_clauses"),
    ("proud", ["proud", "tired", "afraid", "silent"], "feeling_adjective", "comparatives_superlatives"),
    ("project", ["project", "journey", "lesson", "surface"], "project_noun", "pronouns"),
    ("achievement", ["achievement", "attention", "argument", "adventure"], "achievement_noun", "with_compound"),
]

GRAMMAR_TEXT = (
    "Community gardens ① popular in many cities for many years. They give people "
    "a chance to grow their own food and meet their neighbours. A garden ② on "
    "unused land last year is now used by more than fifty families. People work "
    "together because the space ③ by everyone. Before planting, they must decide "
    "what ④ and where each plant should go. Some volunteers ⑤ in the garden for "
    "two years and know its soil well. They explain that young plants ⑥ protection "
    "from strong wind. Everyone is asked to keep the paths clear so that all "
    "visitors can move ⑦. The garden is not only beautiful ⑧ also useful. It teaches "
    "children where food comes from, and it reminds adults ⑨ about waste. If more "
    "residents join next season, the project ⑩ even stronger."
)

GRAMMAR_QA = [
    ("have become", ["have become", "had become", "will become", "are becoming"], "tense_system", "for many years 表示动作持续到现在，应使用现在完成时。", "现在完成时"),
    ("built", ["build", "building", "built", "to build"], "past_participle_nonfinite", "garden 与 build 是被动关系，过去分词 built 作后置定语。", "过去分词作定语"),
    ("is shared", ["shares", "shared", "is shared", "will share"], "passive_voice_tenses", "space 与 share 是被动关系，整句为一般现在时，因此使用 is shared。", "一般现在时被动语态"),
    ("to grow", ["grow", "growing", "to grow", "grown"], "infinitive_nonfinite", "what 后使用不定式表示需要种植的内容，to grow 符合结构。", "不定式作宾语"),
    ("have worked", ["work", "worked", "have worked", "will work"], "tense_system", "for two years 表示从过去持续到现在，应使用现在完成时。", "现在完成时"),
    ("need", ["need", "needs", "needed", "needing"], "subject_verb_agreement", "主语 young plants 为复数，一般现在时谓语使用 need。", "主谓一致"),
    ("safely", ["safe", "safety", "safely", "unsafe"], "word_formation", "move 是动词，需要用副词 safely 修饰。", "副词化"),
    ("but", ["and", "but", "or", "so"], "conjunctions", "not only ... but also ... 是固定并列结构。", "并列连词"),
    ("to think", ["think", "thinking", "to think", "thought"], "infinitive_nonfinite", "remind sb to do sth 是固定结构，因此使用 to think。", "不定式作宾补"),
    ("will become", ["becomes", "became", "will become", "would have become"], "subjunctive_basic_if", "条件句描述将来可能发生的结果，主句使用一般将来时 will become。", "条件句中的将来表达"),
]

GAP_TEXT = (
    "A school wants to start a weekend reading club. The plan explains how "
    "students can join and what they should bring. First, interested students "
    "should write their names on the notice board. (1) The club will then arrange "
    "a short meeting. At the meeting, members will choose books together. "
    "(2) Group leaders will help younger students find books that are right for "
    "them. The club will meet every Saturday morning in the library. (3) Students "
    "are expected to return the books they borrow. At the end of each month, the "
    "group will discuss what they have read. (4) Everyone can speak for two "
    "minutes about a favourite part. New members are always welcome. (5) The "
    "school hopes the club will help students enjoy reading and share ideas."
)

GAP_OPTIONS = [
    "A. This gives everyone time to prepare.",
    "B. The books should be returned on time.",
    "C. It also gives them a chance to make new friends.",
    "D. They can ask questions when they are unsure.",
    "E. A favourite story may be shared at the meeting.",
    "F. This simple step helps the organizers plan.",
    "G. The club has already become popular.",
]

GAP_QA = [
    ("F", "transition", "前文要求学生在公告板上写名字，下一步自然是帮助组织者安排活动。", "该句承接报名后的活动安排。"),
    ("C", "addition", "该段在补充小组长帮助学生的另一项好处。", "所补句子应与前一句形成递进关系。"),
    ("D", "support", "学生借书前可能需要向小组长寻求帮助。", "该句提供借书前的实际指导。"),
    ("A", "sequence", "限制每人发言两分钟，可以为下一位成员留下准备时间。", "该句体现了发言时间安排带来的结果。"),
    ("B", "closing", "最后应落到学校希望学生享受阅读并分享想法这一目的。", "该句总结阅读俱乐部的预期成果。"),
]

CLOZE_2_TEXT = (
    "When our town opened a bike library last year, few people expected it to "
    "become so popular. The idea is simple: residents can borrow a bike for a "
    "day and return it to any station. At first there were only twenty (1), but "
    "demand grew quickly. Volunteers check every bike (2) so that lights work "
    "well. (3) a bike is damaged, it is moved to a repair area. "
    "People must lock it after each trip and avoid (4) on narrow streets. The "
    "service has (5) become part of daily life for many workers. One student says "
    "cycling has (6) her save money and stay active. Another person was (7) by how "
    "quiet the streets felt. (8) blocking entrances, people leave a full bike "
    "at the next station. The map shows (9) stations are busiest and when more "
    "bikes are needed. If residents continue to use the service, the town "
    "(10) more stations next year. Volunteers also teach children about road (11). "
    "A bike can make short journeys more (12), and it gives neighbours a chance "
    "to know their (13). The project is not only transport; it is also a small "
    "(14) in how people understand (15) transport."
)

CLOZE_2_QA = [
    ("bikes", ["bike", "bikes", "biking", "biked"], "fleet_noun", "subject_verb_agreement"),
    ("carefully", ["careful", "carefully", "carefulness", "careless"], "inspection_adverb", "word_formation"),
    ("If", ["If", "Although", "Because", "Unless"], "condition", "adverbial_clauses"),
    ("riding", ["ride", "riding", "rode", "ridden"], "avoid_pattern", "v_ing_nonfinite"),
    ("already", ["already", "instead", "hardly", "perhaps"], "completion_adverb", "articles"),
    ("helped", ["help", "helped", "helping", "helps"], "present_perfect_result", "tense_system"),
    ("surprised", ["surprising", "surprised", "surprise", "surprisingly"], "passive_feeling", "passive_voice_tenses"),
    ("Instead of", ["Instead of", "Because of", "In spite", "According to"], "contrast_preposition", "prepositions"),
    ("which", ["which", "who", "whose", "when"], "station_relative", "relative_clauses_defining"),
    ("will add", ["adds", "added", "will add", "would add"], "future_action", "subjunctive_basic_if"),
    ("safety", ["safe", "safety", "safely", "unsafe"], "road_safety_noun", "articles"),
    ("convenient", ["convenient", "convenience", "conveniently", "inconvenient"], "convenience_adjective", "word_formation"),
    ("community", ["community", "communicate", "communication", "communal"], "local_community", "pronouns"),
    ("step", ["step", "reason", "order", "surface"], "progress_noun", "comparatives_superlatives"),
    ("public", ["public", "private", "strange", "secret"], "public_transport", "with_compound"),
]

GRAMMAR_2_TEXT = (
    "The Green Club ① popular since it began three years ago. Old boxes ② from "
    "local shops are used to grow small plants. Each box ③ carefully before soil "
    "is added. Members work together ④ the project safe and clean. Some students "
    "⑤ more than forty plants for two years and keep detailed records. The number "
    "of active members ⑥ now over eighty. Students plan each activity ⑦ so that "
    "everyone knows what to do. The club is small ⑧ its influence is growing. "
    "Members invite younger students ⑨ the weekend workshops. If every class took "
    "part, the school garden ⑩ an even better place for learning. The students also "
    "keep a simple notebook so that future members can learn from their experience. "
    "They also ask every class to record the number of new plants."
)

GRAMMAR_2_QA = [
    ("has become", ["became", "has become", "will become", "is becoming"], "tense_system", "since 引导的时间起点要求主句使用现在完成时。", "现在完成时"),
    ("collected", ["collect", "collecting", "collected", "to collect"], "past_participle_nonfinite", "boxes 与 collect 是被动关系，过去分词 collected 作后置定语。", "过去分词作定语"),
    ("is checked", ["checks", "checked", "is checked", "will check"], "passive_voice_tenses", "box 是动作承受者，使用一般现在时被动 is checked。", "一般现在时被动"),
    ("to keep", ["keep", "keeping", "to keep", "kept"], "infinitive_nonfinite", "work together to do 表示协作目的，使用不定式。", "不定式作目的状语"),
    ("have grown", ["grow", "grew", "have grown", "will grow"], "tense_system", "for two years 表示持续到现在，使用现在完成时。", "现在完成时"),
    ("is", ["is", "are", "was", "were"], "subject_verb_agreement", "中心词 number 为单数，谓语使用 is。", "主谓一致"),
    ("carefully", ["careful", "carefully", "carefulness", "careless"], "word_formation", "plan 是动词，需要副词 carefully 修饰。", "副词化"),
    ("but", ["and", "but", "or", "so"], "conjunctions", "small 与 growing influence 构成转折关系。", "并列连词"),
    ("to join", ["join", "joining", "to join", "joined"], "infinitive_nonfinite", "invite sb to do sth 是固定结构。", "不定式作宾补"),
    ("would become", ["became", "would become", "will become", "has become"], "subjunctive_basic_if", "if 从句使用过去式时，主句使用 would do 表示非真实条件。", "基础虚拟语气"),
]

READING_SPECS = [
    {
        "group": "DEMO-READING-01",
        "text": (
            "A school in Guangzhou changed its morning schedule after teachers noticed "
            "that many students arrived tired. The first lesson now starts twenty minutes "
            "later, and the time before class is used for reading or quiet study. "
            "Students are not allowed to use the extra time for games or shopping. After "
            "one term, teachers reported that students answered questions more actively "
            "and slept in class less often. The school also asked families to keep "
            "regular sleep times. Some parents worried that a later start would make the "
            "school day end too late, so sports clubs were moved to a shorter lunch break. "
            "The head teacher said the change was not only about sleeping longer. It was "
            "about helping students arrive ready to think, and about teaching them to plan "
            "their evenings honestly."
        ),
        "questions": [
            ("Why did the school change its schedule?", ["Students arrived tired.", "Sports clubs were closed.", "Teachers wanted longer holidays.", "Parents asked for more homework."], "A", "首段说明教师发现许多学生到校时很疲惫，因此调整时间表。", "reading_purpose", "articles", 1),
            ("What may students do before the first lesson?", ["Play online games.", "Read or prepare quietly.", "Go shopping.", "Leave school."], "B", "原文说明课前时间用于阅读或安静准备。", "reading_detail", "relative_clauses_defining", 2),
            ("Why were sports clubs moved?", ["To shorten the school day.", "To give students more homework.", "To reduce morning lessons.", "To improve the weather."], "A", "原文说家长担心放学太晚，因此体育社团被安排到午间。", "reading_inference", "adverbial_clauses", 3),
            ("What does the head teacher value most?", ["Longer sleep alone.", "Students arriving ready to think.", "Closing sports clubs.", "Starting every class late."], "B", "校长强调重点不是单纯多睡，而是让学生到校后准备好思考。", "reading_main_idea", "cleft_basic", 3),
        ],
    },
    {
        "group": "DEMO-READING-02",
        "text": (
            "A library in a small town now lends more than books. People can borrow a "
            "simple repair kit containing a lamp, hand tools, and written instructions. "
            "The idea came from a retired engineer who noticed that people often throw "
            "away small objects because repairing them seemed difficult. A library member "
            "can keep a kit for three days. Before taking one home, the person watches a "
            "short safety video. Staff members say the project has two aims: saving "
            "money and reducing waste. Not every repair succeeds, but people learn how "
            "products are built. One teenager repaired a desk lamp with her father and "
            "then helped a neighbour fix a chair. The engineer believes that a library "
            "should not only store knowledge; it should help people share useful skills."
        ),
        "questions": [
            ("What can people borrow besides books?", ["A bicycle.", "A repair kit.", "A computer.", "A desk lamp."], "B", "第二句明确说读者可以借用维修工具包。", "reading_detail", "relative_clauses_defining", 1),
            ("What must a person do before taking a kit home?", ["Pay for new tools.", "Watch a safety video.", "Bring a neighbour.", "Read three books."], "B", "原文说借出前必须观看十分钟安全视频。", "reading_detail", "passive_voice_tenses", 2),
            ("What is one aim of the project?", ["Selling more lamps.", "Reducing waste.", "Creating a repair shop.", "Replacing libraries."], "B", "工作人员说明项目目标包括省钱和减少浪费。", "reading_detail", "noun_clauses", 3),
            ("What does the retired engineer want the library to do?", ["Store more books.", "Employ more staff.", "Help people share practical skills.", "Sell tools to families."], "C", "结尾强调图书馆应帮助人们分享实用技能。", "reading_main_idea", "infinitive_nonfinite", 3),
        ],
    },
    {
        "group": "DEMO-READING-03",
        "text": (
            "City trees are often planted for beauty, but their value goes much further. "
            "On hot days, leaves help streets stay cooler. Roots hold "
            "soil in place during heavy rain, reducing the risk of sudden flooding. Trees "
            "also create small habitats for birds and insects. However, a young tree needs "
            "care for several years. If it is planted in a narrow space, its roots may "
            "damage pipes or streets. Some cities therefore choose smaller species for "
            "busy streets and leave larger ones for parks. Residents can help by reporting "
            "damaged branches and by avoiding any extra digging near roots. Planting a "
            "tree is a quick event, but keeping it healthy is a long promise shared by "
            "the whole neighbourhood."
        ),
        "questions": [
            ("What is one benefit of city trees on hot days?", ["They reduce shade.", "They cool streets.", "They stop all rain.", "They replace parks."], "B", "第二句说明树叶遮阴并帮助街道降温。", "reading_detail", "articles", 1),
            ("How can tree roots help during heavy rain?", ["They hold soil in place.", "They increase traffic.", "They damage every pipe.", "They remove insects."], "A", "树根在暴雨中固定土壤，减少突发洪涝风险。", "reading_cause_effect", "adverbial_clauses", 2),
            ("Why do some cities use smaller trees on busy streets?", ["To attract more birds.", "To avoid damage to pipes and pavements.", "To make parks smaller.", "To stop residents reporting damage."], "B", "狭窄空间中的大树根部可能破坏管道和人行道，因此选择较小树种。", "reading_inference", "comparatives_superlatives", 3),
            ("What is the main message of the passage?", ["Trees require a shared long-term commitment.", "Only parks should contain trees.", "Trees are planted mainly for decoration.", "Residents should remove old trees."], "A", "末句强调种树是短事件，维护却是社区共同承担的长期承诺。", "reading_main_idea", "infinitive_nonfinite", 3),
        ],
    },
    {
        "group": "DEMO-READING-04",
        "text": (
            "Food can tell the story of a family without using words. At a community food "
            "fair, students prepared dishes that their families had taught them to "
            "make. Each group placed a short note beside the food. The notes explained "
            "where the recipe came from and which ingredients had been changed after the "
            "family moved to Guangdong. Guests could taste a dish only after reading its "
            "story. Staff hoped this rule would slow people down and start "
            "conversations. One student used less sugar than her grandmother did because "
            "fresh fruit was available. Another kept the same soup but added local plants. "
            "The recipes were different from the originals, yet the project was never about "
            "copying the past exactly. It was about carrying memories into a new place and "
            "letting other people understand them."
        ),
        "questions": [
            ("What did each group put beside its food?", ["A price list.", "A short recipe story.", "A family photo.", "A school timetable."], "B", "每组食物旁放置一张解释来源和变化的短说明。", "reading_detail", "articles", 1),
            ("Why did staff ask guests to read before tasting?", ["To check prices.", "To start conversations.", "To finish quickly.", "To hide the recipes."], "B", "组织者希望放慢节奏并促成交流。", "reading_purpose", "infinitive_nonfinite", 2),
            ("How was one student's dish different from her grandmother's?", ["It had no fruit.", "It used less sugar.", "It was served cold.", "It contained no soup."], "B", "一名学生因为能买到新鲜水果而减少了糖的用量。", "reading_detail", "comparatives_superlatives", 3),
            ("What was the project mainly about?", ["Carrying family memories into a new place.", "Selling traditional food.", "Teaching professional cooking.", "Recording prices."], "A", "最后一句说明项目重在把记忆带入新环境并让他人理解。", "reading_main_idea", "infinitive_nonfinite", 3),
        ],
    },
    {
        "group": "DEMO-READING-05",
        "text": (
            "Many people believe that exercise has to be difficult to be useful. A simple "
            "walk, however, can improve both feelings and health. Research suggests that short "
            "walks after meals may help the body control sugar levels. Walking also gives "
            "people a break from screens and creates chances to meet neighbours. The "
            "greatest problem is often starting. Health experts suggest choosing a familiar "
            "route and walking for ten minutes. Once that becomes a habit, people can add "
            "a few minutes each week. Comfortable shoes matter more than expensive sports "
            "clothes. It is also easier to continue when a friend walks at the same time. "
            "The aim is not to compete with anyone. It is to make movement a normal part "
            "of the day, one small choice at a time."
        ),
        "questions": [
            ("What common belief does the passage question?", ["Walking is useful.", "Exercise must be difficult.", "Friends make exercise easier.", "Shoes affect walking."], "B", "开头指出许多人以为运动必须很难才有用，文章对此提出不同看法。", "reading_purpose", "noun_clauses", 1),
            ("What may a short walk after a meal help with?", ["Screen size.", "Sugar levels.", "Shoe prices.", "Traffic speed."], "B", "第二段说饭后短距离步行可能帮助身体控制血糖。", "reading_detail", "articles", 2),
            ("What do health experts suggest first?", ["Buying expensive clothes.", "Walking ten minutes on a familiar route.", "Competing with a friend.", "Walking for an hour."], "B", "专家建议先选择熟悉路线并步行十分钟。", "reading_detail", "comparatives_superlatives", 3),
            ("What is the main idea of the passage?", ["Exercise should be competitive.", "Small walking habits can make movement normal.", "People should avoid screens completely.", "Expensive clothes improve health."], "B", "全文强调从小的步行习惯开始，让运动成为日常生活的一部分。", "reading_main_idea", "infinitive_nonfinite", 3),
        ],
    },
]

GAP_2_TEXT = (
    "A youth group wants to improve an empty corner of the school garden. First, "
    "members will measure the area and list the tools they need. (1) Next, they will "
    "turn the soil and remove stones before planting anything. (2) The group plans to "
    "grow vegetables that students can use in cooking lessons. (3) Different classes "
    "will take turns looking after the plants. (4) At the end of the term, the group "
    "will hold an open garden day. (5) The project should teach students that small "
    "daily actions can create a shared space everyone is proud of."
)

GAP_2_OPTIONS = [
    "A. They will also ask the science teacher for advice.",
    "B. This work will make the ground ready for young plants.",
    "C. It will also provide fresh food for the school kitchen.",
    "D. This arrangement prevents one class from doing all the work.",
    "E. Families and teachers will be invited to see the result.",
    "F. The first step is to talk with the person responsible for the garden.",
    "G. The garden has already won several national competitions.",
]

GAP_2_QA = [
    ("A", "addition", "测量和列工具清单后，还需要咨询科学老师的意见。", "空白位于第一步与第二步之间。"),
    ("B", "explanation", "松土和清理石头是为种植准备土壤。", "空白应解释前一步的目的。"),
    ("C", "benefit", "种植蔬菜还能为学校厨房提供新鲜食物。", "空白承接蔬菜可用于烹饪课。"),
    ("D", "explanation", "轮流照料可以避免一个班级承担全部劳动。", "空白解释班级轮值的意义。"),
    ("E", "closing", "开放日会邀请家庭和教师观看成果。", "空白补充开放日的具体对象。"),
]

CLOZE_BOOKS = [
    "选必二 U1",
    "选必二 U2",
    "选必二 U3",
    "选必二 U4",
    "选必二 U5",
    "选必二 U1",
    "选必二 U3",
    "选必一 U1",
    "选必一 U2",
    "选必一 U3",
    "选必一 U4",
    "选必一 U5",
    "必修一 U4",
    "必修三 U2",
    "跨册综合",
]

GRAMMAR_BOOKS = [
    "选必二 U2",
    "选必二 U4",
    "选必二 U5",
    "选必一 U1",
    "选必一 U2",
    "选必一 U3",
    "选必一 U4",
    "必修二 U4",
    "必修三 U1",
    "必修三 U4",
]

READING_BOOKS = ["选必二 U1", "选必二 U3", "选必二 U5", "必修二 U2"]
GAP_BOOKS = ["选必二 U1", "选必二 U2", "选必二 U3", "选必二 U4", "必修二 U1"]
CLOZE_DIFFICULTIES = [1, 1, 2, 2, 2, 3, 3, 3, 3, 3, 4, 4, 4, 5, 5]
GRAMMAR_DIFFICULTIES = [1, 1, 2, 2, 2, 3, 3, 3, 3, 4]
READING_DIFFICULTIES = [1, 2, 3, 3]
GAP_DIFFICULTIES = [1, 1, 3, 3, 3]
GAP_TAG_MAP = {
    1: "adverbial_clauses",
    2: "conjunctions",
    3: "pronouns",
    4: "passive_voice_tenses",
    5: "subject_verb_agreement",
    6: "relative_clauses_defining",
    7: "relative_clauses_non_defining",
    8: "passive_voice_tenses",
    9: "past_participle_nonfinite",
    10: "v_ing_nonfinite",
}


CLOZE_REASONS = {
    "team_noun": "small groups 表示把学生分成小组。",
    "material_noun": "该名词与从沙滩收集废弃物的语境一致。",
    "manner_adverb": "此处需要副词修饰 worked。",
    "concession": "前后句是让步关系，Although 符合逻辑。",
    "reporting_verb": "该动词与教师建议记录结果这一语境一致。",
    "decision_noun": "该名词与 make a decision 的固定搭配一致。",
    "observation_verb": "该动词表示在水边注意到一群鸟。",
    "verb_pattern": "avoid doing 表示避免做某事。",
    "time_adverb": "already 与该句完成时语境一致。",
    "object_preposition": "without 表示没有使用塑料袋。",
    "effort_noun": "该名词与团队共同付出的努力相呼应。",
    "purpose_verb": "reach 表示让信息传播得更远。",
    "feeling_adjective": "proud 与完成清理后的感受一致。",
    "project_noun": "该名词与前文的清理活动相呼应。",
    "achievement_noun": "该名词总结完成清理后的成就感。",
    "fleet_noun": "twenty bicycles 表示可供借用的自行车数量。",
    "inspection_adverb": "inspect 是动词，需要副词 regularly 修饰。",
    "condition": "此处表示自行车损坏后的条件，If 符合逻辑。",
    "avoid_pattern": "avoid doing 表示避免做某事。",
    "completion_adverb": "already 与现在完成时搭配。",
    "present_perfect_result": "has helped 表示过去行为对现在产生的结果。",
    "passive_feeling": "rider 感到惊讶，使用 surprised。",
    "contrast_preposition": "Instead of 引出与后半句替代关系相符的动名词。",
    "station_relative": "which 指代 stations 并在从句中作主语。",
    "future_action": "条件句描述将来，主句使用 will add。",
    "road_safety_noun": "road safety 表示道路安全。",
    "convenience_adjective": "make journeys more convenient 表示让出行更方便。",
    "local_community": "their 指代邻里，community 表示社区。",
    "progress_noun": "small step 表示理解公共交通的一小步。",
    "public_transport": "public transport 表示公共交通。",
}


def _explanation(answer: str, point: str) -> str:
    reason = CLOZE_REASONS.get(point, "该选项与句子结构和上下文最为匹配。")
    return f"正确答案是 {answer}。{reason}其余选项在语境或语法上不合适。"


def _cloze_questions(
    *,
    start: int,
    group_id: str,
    passage: str,
    qa: list[tuple[str, list[str], str, str]],
) -> list[DemoQuestion]:
    questions = []
    for local_number, (answer, options, point, tag) in enumerate(qa, start=1):
        questions.append(
            DemoQuestion(
                id=f"{QUESTION_PREFIX}C{start + local_number - 1:02d}",
                bank_id=BANK_ID,
                type="cloze",
                passage_group_id=group_id,
                passage=passage,
                stem=f"选择第 {local_number} 空最合适的选项。",
                options=options,
                answer=answer,
                explanation=_explanation(answer, point),
                knowledge_points=[point],
                grammar_tags=[tag],
                book_source=CLOZE_BOOKS[local_number - 1],
                difficulty=CLOZE_DIFFICULTIES[local_number - 1],
            )
        )
    return questions


def _grammar_questions(
    *,
    start: int,
    group_id: str,
    passage: str,
    qa: list[tuple[str, list[str], str, str, str]],
) -> list[DemoQuestion]:
    questions = []
    for local_number, (answer, options, tag, explanation, point) in enumerate(qa, start=1):
        questions.append(
            DemoQuestion(
                id=f"{QUESTION_PREFIX}G{start + local_number - 1:02d}",
                bank_id=BANK_ID,
                type="grammar_fill",
                passage_group_id=group_id,
                passage=passage,
                stem=f"选择 {chr(0x2460 + local_number - 1)} 处最合适的选项。",
                options=options,
                answer=answer,
                explanation=f"正确答案是 {answer}。{explanation}",
                knowledge_points=[point],
                grammar_tags=[tag],
                book_source=GRAMMAR_BOOKS[local_number - 1],
                difficulty=GRAMMAR_DIFFICULTIES[local_number - 1],
            )
        )
    return questions


def _gap_questions(
    *,
    start: int,
    group_id: str,
    passage: str,
    options: list[str],
    qa: list[tuple[str, str, str, str]],
) -> list[DemoQuestion]:
    questions = []
    for local_number, (answer, link_type, fit, point) in enumerate(qa, start=1):
        questions.append(
            DemoQuestion(
                id=f"{QUESTION_PREFIX}P{start + local_number - 1:02d}",
                bank_id=BANK_ID,
                type="gap_fill",
                passage_group_id=group_id,
                passage=passage,
                stem=f"选择最适合第 {local_number} 空的句子。",
                options=options,
                answer=answer,
                explanation=f"正确答案是 {answer}。{fit}{point}",
                knowledge_points=[f"gap_fill_{link_type}"],
                grammar_tags=[
                    GAP_TAG_MAP[
                        local_number + (0 if group_id == "DEMO-GAP-01" else 5)
                    ]
                ],
                book_source=GAP_BOOKS[local_number - 1],
                difficulty=GAP_DIFFICULTIES[local_number - 1],
            )
        )
    return questions


def _reading_questions() -> list[DemoQuestion]:
    questions = []
    ordinal = 0
    for spec in READING_SPECS:
        for local_number, (
            stem,
            options,
            answer,
            explanation,
            point,
            tag,
            difficulty,
        ) in enumerate(spec["questions"], start=1):
            ordinal += 1
            questions.append(
                DemoQuestion(
                    id=f"{QUESTION_PREFIX}R{ordinal:02d}",
                    bank_id=BANK_ID,
                    type="reading",
                    passage_group_id=spec["group"],
                    passage=spec["text"],
                    stem=stem,
                    options=options,
                    answer=answer,
                    explanation=explanation,
                    knowledge_points=[point],
                    grammar_tags=[tag],
                    book_source=READING_BOOKS[local_number - 1],
                    difficulty=difficulty,
                )
            )
    return questions


def build_demo_questions() -> list[DemoQuestion]:
    questions: list[DemoQuestion] = []
    questions.extend(
        _cloze_questions(
            start=1,
            group_id="DEMO-CLOZE-01",
            passage=CLOZE_TEXT,
            qa=CLOZE_QA,
        )
    )
    questions.extend(
        _cloze_questions(
            start=16,
            group_id="DEMO-CLOZE-02",
            passage=CLOZE_2_TEXT,
            qa=CLOZE_2_QA,
        )
    )
    questions.extend(
        _grammar_questions(
            start=1,
            group_id="DEMO-GRAMMAR-01",
            passage=GRAMMAR_TEXT,
            qa=GRAMMAR_QA,
        )
    )
    questions.extend(
        _grammar_questions(
            start=11,
            group_id="DEMO-GRAMMAR-02",
            passage=GRAMMAR_2_TEXT,
            qa=GRAMMAR_2_QA,
        )
    )
    questions.extend(_reading_questions())
    questions.extend(
        _gap_questions(
            start=1,
            group_id="DEMO-GAP-01",
            passage=GAP_TEXT,
            options=GAP_OPTIONS,
            qa=GAP_QA,
        )
    )
    questions.extend(
        _gap_questions(
            start=6,
            group_id="DEMO-GAP-02",
            passage=GAP_2_TEXT,
            options=GAP_2_OPTIONS,
            qa=GAP_2_QA,
        )
    )
    return questions


def demo_bank() -> dict:
    return {
        "bank_id": BANK_ID,
        "name": "Demo Bank",
        "version": "1",
        "status": "active",
        "target_size": 80,
        "difficulty_profile": "standard",
        "created_at": datetime(2026, 11, 7, tzinfo=timezone.utc).isoformat(),
        "questions": build_demo_questions(),
    }
