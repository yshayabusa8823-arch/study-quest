import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


st.set_page_config(
    page_title="Study Quest",
    page_icon="icon.png",
    layout="centered"
)

SHEET_NAME = "StudyQuestDB"
JST = ZoneInfo("Asia/Tokyo")

if "notice_message" not in st.session_state:
    st.session_state.notice_message = None

if "notice_type" not in st.session_state:
    st.session_state.notice_type = "success"


# =====================
# Google Sheets 接続
# =====================
@st.cache_resource
def connect_sheets():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scope
    )

    client = gspread.authorize(creds)
    spreadsheet = client.open(SHEET_NAME)

    return {
        "logs": spreadsheet.worksheet("logs"),
        "users": spreadsheet.worksheet("users"),
        "subjects": spreadsheet.worksheet("subjects"),
        "active_sessions": spreadsheet.worksheet("active_sessions"),
        "tomorrow_notes": spreadsheet.worksheet("tomorrow_notes"),
    }



sheets = connect_sheets()
logs_sheet = sheets["logs"]
users_sheet = sheets["users"]
subjects_sheet = sheets["subjects"]
sessions_sheet = sheets["active_sessions"]
tomorrow_notes_sheet = sheets["tomorrow_notes"]


# =====================
# データ読み込み
# =====================
@st.cache_data(ttl=60)
def load_sheet_cached(sheet_name, columns):
    sheet = sheets[sheet_name]
    records = sheet.get_all_records()

    if not records:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(records)

    for col in columns:
        if col not in df.columns:
            df[col] = ""

    return df[columns]


def load_logs():
    df = load_sheet_cached(
        "logs",
        ["user_id", "date", "subject", "hours", "focus", "memo"]
    )

    if not df.empty:
        df["hours"] = pd.to_numeric(df["hours"], errors="coerce").fillna(0)
        df["focus"] = pd.to_numeric(df["focus"], errors="coerce").fillna(0)

    return df


def load_users():
    df = load_sheet_cached(
        "users",
        [
            "user_id",
            "name",
            "weekly_goal",
            "programming_ratio",
            "math_ratio",
            "statistics_ratio",
            "english_ratio",
            "other_ratio"
        ]
    )

    numeric_cols = [
        "weekly_goal",
        "programming_ratio",
        "math_ratio",
        "statistics_ratio",
        "english_ratio",
        "other_ratio"
    ]

    for col in numeric_cols:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        ).fillna(0)

    return df

    if not df.empty:
        df["weekly_goal"] = pd.to_numeric(
            df["weekly_goal"],
            errors="coerce"
        ).fillna(25)

    return df


def load_subjects():
    return load_sheet_cached(
        "subjects",
        ["user_id", "subject"]
    )


def load_sessions():
    return load_sheet_cached(
        "active_sessions",
        ["user_id", "subject", "start_time", "focus", "memo"]
    )

def load_tomorrow_notes():
    return load_sheet_cached(
        "tomorrow_notes",
        ["user_id", "date", "note"]
    )


# =====================
# Google Sheets 書き込み
# =====================
def append_log(user_id, log_date, subject, hours, focus, memo):
    logs_sheet.append_row([
        user_id,
        str(log_date),
        subject,
        float(hours),
        int(focus),
        memo
    ])


def append_subject(user_id, subject):
    subjects_sheet.append_row([user_id, subject])


def append_tomorrow_note(user_id, note):
    tomorrow_notes_sheet.append_row([
        user_id,
        str(datetime.now(JST).date()),
        note
    ])

def start_session(user_id, subject, focus, memo):
    sessions_sheet.append_row([
        user_id,
        subject,
        datetime.now(JST).isoformat(timespec="seconds"),
        int(focus),
        memo
    ])

def delete_session_by_sheet_row(sheet_row):
    sessions_sheet.delete_rows(sheet_row)

def update_session_memo_by_sheet_row(sheet_row, memo):
    sessions_sheet.update(
        f"E{sheet_row}",
        [[memo]]
    )

def delete_session_by_sheet_row(sheet_row):
    sessions_sheet.delete_rows(sheet_row)


def delete_log_by_sheet_row(sheet_row):
    logs_sheet.delete_rows(sheet_row)


def upsert_user(
    user_id,
    name,
    weekly_goal,
    programming_ratio,
    math_ratio,
    statistics_ratio,
    english_ratio,
    other_ratio
):
    users = load_users()

    target_row = None

    for i, row in users.iterrows():
        if row["user_id"] == user_id:
            target_row = i + 2
            break

    values = [[
        user_id,
        name,
        float(weekly_goal),
        int(programming_ratio),
        int(math_ratio),
        int(statistics_ratio),
        int(english_ratio),
        int(other_ratio)
    ]]

    if target_row:
        users_sheet.update(
            f"A{target_row}:H{target_row}",
            values
        )
    else:
        users_sheet.append_row(values[0])

CATEGORY_DEFS = {
    "programming": {
        "label": "プログラミング",
        "icon": "💻",
        "keywords": ["プログラミング", "Python", "python", "AI", "機械学習", "アプリ"]
    },
    "math": {
        "label": "数学",
        "icon": "📐",
        "keywords": ["線形代数", "微分積分", "数学"]
    },
    "statistics": {
        "label": "統計",
        "icon": "📊",
        "keywords": ["統計", "統計学", "データ分析"]
    },
    "english": {
        "label": "英語",
        "icon": "🇺🇸",
        "keywords": ["英語", "TOEFL", "TOEIC", "IELTS", "英単語", "リスニング"]
    },
    "other": {
        "label": "その他",
        "icon": "📚",
        "keywords": []
    },
}


def categorize_subject(subject):
    subject = str(subject)

    for category_key, category in CATEGORY_DEFS.items():
        if category_key == "other":
            continue

        for keyword in category["keywords"]:
            if keyword in subject:
                return category_key

    return "other"


def make_balance_summary(week_logs, weekly_goal, ratios):
    category_actuals = {
        key: 0.0 for key in CATEGORY_DEFS.keys()
    }

    if not week_logs.empty:
        temp = week_logs.copy()
        temp["category"] = temp["subject"].apply(categorize_subject)

        grouped = temp.groupby("category")["hours"].sum()

        for category_key, hours in grouped.items():
            category_actuals[category_key] = float(hours)

    rows = []

    for category_key, category in CATEGORY_DEFS.items():
        ratio = int(ratios.get(category_key, 0))
        target = float(weekly_goal) * ratio / 100
        actual = category_actuals.get(category_key, 0.0)
        shortage = max(target - actual, 0)
        achievement = (
            0 if target == 0
            else actual / target * 100
        )

        rows.append({
            "key": category_key,
            "label": category["label"],
            "icon": category["icon"],
            "ratio": ratio,
            "target": target,
            "actual": actual,
            "shortage": shortage,
            "achievement": achievement,
        })

    return rows

# =====================
# 計算関数
# =====================
def get_week_range(today):
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return start, end


def calc_streak(user_logs):
    if user_logs.empty:
        return 0

    dates = sorted(
        pd.to_datetime(user_logs["date"]).dt.date.unique(),
        reverse=True
    )

    today_jst = datetime.now(JST).date()

    if today_jst not in dates:
        today_jst = today_jst - timedelta(days=1)

    streak = 0
    current = today_jst

    while current in dates:
        streak += 1
        current -= timedelta(days=1)

    return streak


def calc_level(total_hours):
    level = int(total_hours // 10) + 1
    next_level_total = level * 10
    current_level_total = (level - 1) * 10
    progress_in_level = total_hours - current_level_total
    required_for_level = next_level_total - current_level_total

    return level, progress_in_level, required_for_level, next_level_total


def badge(icon, title, earned, note):
    return {
        "icon": icon,
        "title": title,
        "earned": earned,
        "note": note
    }


def get_badge_status(total_hours, streak, weekly_total, weekly_goal, user_logs):
    all_badges = []

    hour_badges = [
        (1, "🌱", "はじめの一歩"),
        (5, "🐣", "助走開始"),
        (10, "📚", "10時間突破"),
        (25, "🥉", "25時間突破"),
        (50, "🏆", "50時間突破"),
        (75, "🥈", "75時間突破"),
        (100, "👑", "100時間突破"),
        (150, "💪", "努力家"),
        (200, "🔥", "継続の達人"),
        (300, "💎", "300時間突破"),
        (500, "🚀", "500時間突破"),
        (1000, "🌌", "1000時間の境地"),
    ]

    for target, icon, title in hour_badges:
        earned = total_hours >= target
        remain = max(target - total_hours, 0)
        note = "獲得済み" if earned else f"あと {remain:.1f}h"
        all_badges.append(badge(icon, title, earned, note))

    streak_badges = [
        (2, "🧩", "2日連続"),
        (3, "🔥", "継続の火"),
        (7, "🗓️", "一週間継続"),
        (14, "⚔️", "二週間継続"),
        (30, "🏯", "習慣化成功"),
        (50, "🦁", "継続王"),
        (100, "👑", "継続皇帝"),
    ]

    for target, icon, title in streak_badges:
        earned = streak >= target
        remain = max(target - streak, 0)
        note = "獲得済み" if earned else f"あと {remain}日"
        all_badges.append(badge(icon, title, earned, note))

    weekly_badges = [
        (1.0, "🎯", "週間目標達成"),
        (1.2, "🚴", "目標超え"),
        (1.5, "🦅", "大幅達成"),
    ]

    for rate, icon, title in weekly_badges:
        target = weekly_goal * rate
        earned = weekly_total >= target
        remain = max(target - weekly_total, 0)
        note = "獲得済み" if earned else f"あと {remain:.1f}h"
        all_badges.append(badge(icon, title, earned, note))

    if user_logs.empty:
        log_count = 0
        max_focus = 0
        high_focus_count = 0
        max_hours = 0
        subject_totals = pd.Series(dtype=float)
    else:
        log_count = len(user_logs)
        max_focus = user_logs["focus"].max()
        high_focus_count = len(user_logs[user_logs["focus"] >= 90])
        max_hours = user_logs["hours"].max()
        subject_totals = user_logs.groupby("subject")["hours"].sum()

    count_badges = [
        (3, "✍️", "記録初心者"),
        (10, "📘", "記録習慣"),
        (30, "📒", "ログ職人"),
        (50, "🗂️", "記録マスター"),
        (100, "🧾", "記録の鬼"),
    ]

    for target, icon, title in count_badges:
        earned = log_count >= target
        remain = max(target - log_count, 0)
        note = "獲得済み" if earned else f"あと {remain}回"
        all_badges.append(badge(icon, title, earned, note))

    focus_badges = [
        (max_focus >= 90, "⚡", "集中マスター", "集中度90以上"),
        (max_focus >= 100, "🧠", "完全集中", "集中度100"),
        (high_focus_count >= 5, "🔮", "集中の再現性", f"あと {max(5 - high_focus_count, 0)}回"),
        (high_focus_count >= 10, "🧘", "集中の達人", f"あと {max(10 - high_focus_count, 0)}回"),
    ]

    for earned, icon, title, locked_note in focus_badges:
        note = "獲得済み" if earned else locked_note
        all_badges.append(badge(icon, title, earned, note))

    long_badges = [
        (3, "⏳", "3時間クエスト"),
        (5, "🗻", "5時間クエスト"),
        (8, "🐉", "限界突破"),
    ]

    for target, icon, title in long_badges:
        earned = max_hours >= target
        remain = max(target - max_hours, 0)
        note = "獲得済み" if earned else f"1回であと {remain:.1f}h"
        all_badges.append(badge(icon, title, earned, note))

    for subject, hours in subject_totals.items():
        subject_badges = [
            (10, "📖", f"{subject} 10時間"),
            (30, "🎓", f"{subject} 30時間"),
            (50, "🏅", f"{subject} 50時間"),
            (100, "👑", f"{subject} マスター"),
        ]

        for target, icon, title in subject_badges:
            earned = hours >= target
            remain = max(target - hours, 0)
            note = "獲得済み" if earned else f"あと {remain:.1f}h"
            all_badges.append(badge(icon, title, earned, note))

    earned_badges = [b for b in all_badges if b["earned"]]
    locked_badges = [b for b in all_badges if not b["earned"]]

    return earned_badges, locked_badges


# =====================
# CSS
# =====================
st.markdown("""
<style>
.stApp {
    background:
        radial-gradient(circle at 12% 8%, rgba(191, 219, 254, 0.75), transparent 28%),
        radial-gradient(circle at 88% 10%, rgba(224, 242, 254, 0.95), transparent 32%),
        radial-gradient(circle at 50% 95%, rgba(219, 234, 254, 0.85), transparent 34%),

        radial-gradient(circle at 20% 30%, rgba(255,255,255,0.65) 0px, rgba(255,255,255,0) 2px),
        radial-gradient(circle at 80% 22%, rgba(255,255,255,0.55) 0px, rgba(255,255,255,0) 2px),
        radial-gradient(circle at 60% 72%, rgba(255,255,255,0.45) 0px, rgba(255,255,255,0) 2px),
        radial-gradient(circle at 32% 82%, rgba(255,255,255,0.42) 0px, rgba(255,255,255,0) 2px),

        linear-gradient(
            135deg,
            rgba(255,255,255,0.10) 25%,
            transparent 25%,
            transparent 50%,
            rgba(255,255,255,0.06) 50%,
            rgba(255,255,255,0.06) 75%,
            transparent 75%,
            transparent
        ),

        linear-gradient(
            180deg,
            #eef8ff 0%,
            #e8f3ff 45%,
            #f7fbff 100%
        );

    background-size:
        auto,
        auto,
        auto,

        180px 180px,
        240px 240px,
        220px 220px,
        260px 260px,

        120px 120px,

        auto;

    background-attachment: fixed;
}

.block-container {
    padding-top: 0.6rem;
    padding-left: 1rem;
    padding-right: 1rem;
    max-width: 860px;
}

.hero {
    position: relative;
    overflow: hidden;
    background:
        radial-gradient(circle at 80% 30%, rgba(255,255,255,0.72), transparent 22%),
        radial-gradient(circle at 20% 90%, rgba(186,230,253,0.85), transparent 32%),
        linear-gradient(135deg, #dff3ff 0%, #c9e7ff 45%, #b9d8ff 100%);
    padding: 30px;
    border-radius: 34px;
    color: #12305f;
    margin-bottom: 20px;
    box-shadow: 0 18px 45px rgba(59,130,246,0.16);
    border: 1px solid rgba(255,255,255,0.8);
}




.hero h1 {
    font-size: 44px;
    line-height: 0.95;
    margin-bottom: 14px;
    font-weight: 950;
    color: #1d4ed8;
    text-shadow: 0 2px 0 rgba(255,255,255,0.85);
}

.hero h3 {
    margin-top: 0;
    font-weight: 900;
    color: #1e3a8a;
}

.hero p {
    color: #475569;
    font-weight: 750;
}

.mission-card {
    position: relative;
    overflow: hidden;
    background: rgba(255,255,255,0.78);
    padding: 22px;
    border-radius: 30px;
    border: 1px solid rgba(186,230,253,0.95);
    margin-bottom: 18px;
    font-size: 17px;
    box-shadow: 0 14px 32px rgba(59,130,246,0.10);
    backdrop-filter: blur(12px);
}


.stat-card {
    background: rgba(255,255,255,0.86);
    padding: 20px;
    border-radius: 28px;
    box-shadow: 0 14px 32px rgba(59,130,246,0.10);
    border: 1px solid rgba(191,219,254,0.95);
    margin-bottom: 14px;
    backdrop-filter: blur(12px);
}

.stat-label {
    color: #2563eb;
    font-size: 14px;
    font-weight: 900;
    margin-bottom: 12px;
}

.stat-number {
    color: #0f172a;
    font-size: 31px;
    font-weight: 950;
}

.progress-card,
.quest-card,
.study-rank-card,
.record-card {
    background: rgba(255,255,255,0.88);
    border: 1px solid rgba(219,234,254,0.96);
    box-shadow: 0 14px 34px rgba(59,130,246,0.10);
    backdrop-filter: blur(12px);
}

.section-title {
    font-size: 27px;
    font-weight: 950;
    color: #1e3a8a;
    margin-top: 28px;
    margin-bottom: 14px;
}

.badge-pill {
    display: inline-block;
    background: linear-gradient(135deg, #eff6ff, #e0f2fe);
    color: #1e3a8a;
    padding: 10px 14px;
    border-radius: 999px;
    margin: 5px 4px;
    font-weight: 850;
    font-size: 14px;
    border: 1px solid #bfdbfe;
}

.locked-badge-pill {
    display: inline-block;
    background: rgba(255,255,255,0.62);
    color: #94a3b8;
    border: 1px dashed #cbd5e1;
    padding: 10px 14px;
    border-radius: 999px;
    margin: 5px 4px;
    font-weight: 750;
    font-size: 14px;
    opacity: 0.72;
}

.record-card {
    border-radius: 24px;
    padding: 17px 18px;
    margin-bottom: 13px;
}

.record-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
}

.record-subject {
    font-size: 18px;
    font-weight: 950;
    color: #1e3a8a;
}

.record-date {
    font-size: 13px;
    font-weight: 750;
    color: #64748b;
}

.record-meta {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
}

.record-chip {
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    color: #1e40af;
    padding: 7px 11px;
    border-radius: 999px;
    font-size: 13px;
    font-weight: 850;
}

.study-rank-card {
    border-radius: 26px;
    padding: 18px;
    margin-bottom: 14px;
}

.rank-row {
    display: grid;
    grid-template-columns: 52px 1fr auto;
    gap: 12px;
    align-items: center;
}

.rank-badge {
    width: 42px;
    height: 42px;
    border-radius: 16px;
    background: linear-gradient(135deg, #dbeafe, #eff6ff);
    display: flex;
    justify-content: center;
    align-items: center;
    font-size: 19px;
    font-weight: 950;
    color: #2563eb;
}

.rank-title {
    font-size: 18px;
    font-weight: 950;
    color: #0f172a;
}

.rank-sub {
    font-size: 13px;
    font-weight: 750;
    color: #64748b;
    margin-top: 3px;
}

.rank-value {
    font-size: 24px;
    font-weight: 950;
    color: #2563eb;
}

.focus-good {
    color: #16a34a;
}

.focus-mid {
    color: #ca8a04;
}

.focus-low {
    color: #dc2626;
}

button[kind="primary"], .stButton > button {
    border-radius: 999px;
    border: 1px solid rgba(147,197,253,0.9);
    background: linear-gradient(135deg, #60a5fa, #818cf8);
    color: white;
    font-weight: 850;
    box-shadow: 0 10px 24px rgba(59,130,246,0.22);
}

.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 999px;
    padding: 8px 14px;
    background: rgba(255,255,255,0.58);
    border: 1px solid rgba(219,234,254,0.9);
}
            
.stat-card:hover,
.record-card:hover,
.study-rank-card:hover {
    transform: translateY(-4px);
    transition: 0.2s ease;
    box-shadow: 0 18px 38px rgba(59,130,246,0.16);
}
            
.big-progress-card {
    background: rgba(255,255,255,0.9);
    border: 1px solid rgba(219,234,254,0.96);
    border-radius: 30px;
    padding: 22px;
    margin-bottom: 18px;
    box-shadow: 0 16px 38px rgba(59,130,246,0.12);
}

.big-progress-title {
    font-size: 16px;
    font-weight: 900;
    color: #2563eb;
    margin-bottom: 6px;
}

.big-progress-number {
    font-size: 42px;
    font-weight: 950;
    color: #0f172a;
    margin-bottom: 8px;
}


            
.balance-progress-card {
    background: rgba(255,255,255,0.88);
    border: 1px solid rgba(219,234,254,0.96);
    border-radius: 24px;
    padding: 18px;
    margin-bottom: 14px;
    box-shadow: 0 10px 24px rgba(59,130,246,0.08);
}

.balance-progress-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
    font-weight: 900;
    color: #0f172a;
}

.balance-bar-bg {
    width: 100%;
    height: 14px;
    background: #e5edff;
    border-radius: 999px;
    overflow: hidden;
    margin-top: 8px;
}

.balance-bar-fill {
    height: 14px;
    border-radius: 999px;
    background: linear-gradient(
        90deg,
        #60a5fa,
        #818cf8
    );
}

.balance-progress-sub {
    margin-top: 10px;
    font-size: 14px;
    color: #64748b;
    font-weight: 700;
}


            
.stProgress > div > div > div > div {
    background: linear-gradient(
        90deg,
        #2563eb,
        #3b82f6,
        #6366f1
    ) !important;
}

.hero-logo-wrap {
    display: flex;
    align-items: center;
    gap: 1rem;
}

.hero-compass {
    font-size: 4.5rem;
}

.hero-logo-text {
    font-size: 4rem;
    font-weight: 950;
    line-height: 0.95;
    color: #2563eb;
    text-shadow: 0 4px 12px rgba(37,99,235,0.15);
}            
</style>
""", unsafe_allow_html=True)



# =====================
# 初期データ
# =====================
users = load_users()
logs = load_logs()
subjects_df = load_subjects()
sessions_df = load_sessions()
tomorrow_notes_df = load_tomorrow_notes()

default_users = {
    "syun": {"name": "しゅん", "weekly_goal": 25.0},
    "shiori": {"name": "しおり", "weekly_goal": 35.0},
}

default_subjects_map = {
    "syun": ["線形代数", "統計", "微分積分", "法律", "その他"],
    "shiori": [
        "民法",
        "憲法",
        "刑法",
        "民事訴訟法",
        "刑事訴訟法",
        "商法",
        "知的財産法",
        "その他"
    ],
}


# =====================
# サイドバー
# =====================
st.sidebar.title("⚙️ 設定")

if st.sidebar.button("🔄 更新"):
    st.cache_data.clear()
    st.rerun()

user_options = ["syun", "shiori"]
query_user = st.query_params.get("user", "syun")

if query_user not in user_options:
    query_user = "syun"

default_index = user_options.index(query_user)

user_id = st.sidebar.selectbox(
    "ユーザーを選択",
    user_options,
    index=default_index
)

st.query_params["user"] = user_id

user_data = users[users["user_id"] == user_id]

if user_data.empty:

    name = "しゅん"
    weekly_goal = 25

    prog_ratio = 35
    math_ratio = 25
    stat_ratio = 20
    eng_ratio = 15
    other_ratio = 5
else:

    name = user_data.iloc[0]["name"]

    weekly_goal = float(
        user_data.iloc[0]["weekly_goal"]
    )

    prog_ratio = int(
        user_data.iloc[0]["programming_ratio"]
    )

    math_ratio = int(
        user_data.iloc[0]["math_ratio"]
    )

    stat_ratio = int(
        user_data.iloc[0]["statistics_ratio"]
    )

    eng_ratio = int(
        user_data.iloc[0]["english_ratio"]
    )

    other_ratio = int(
        user_data.iloc[0]["other_ratio"]
    )

st.sidebar.divider()
st.sidebar.subheader("プロフィール編集")
st.sidebar.divider()
st.sidebar.subheader("🎯 理想配分")

prog_ratio = st.sidebar.number_input(
    "💻 プログラミング (%)",
    min_value=0,
    max_value=100,
    value=int(prog_ratio),
    step=5
)

math_ratio = st.sidebar.number_input(
    "📐 数学 (%)",
    min_value=0,
    max_value=100,
    value=int(math_ratio),
    step=5
)

stat_ratio = st.sidebar.number_input(
    "📊 統計 (%)",
    min_value=0,
    max_value=100,
    value=int(stat_ratio),
    step=5
)

eng_ratio = st.sidebar.number_input(
    "🇺🇸 英語 (%)",
    min_value=0,
    max_value=100,
    value=int(eng_ratio),
    step=5
)

other_ratio = st.sidebar.number_input(
    "📚 その他 (%)",
    min_value=0,
    max_value=100,
    value=int(other_ratio),
    step=5
)

ratio_total = (
    prog_ratio +
    math_ratio +
    stat_ratio +
    eng_ratio +
    other_ratio
)

if ratio_total != 100:
    st.sidebar.warning(
        f"現在 {ratio_total}%"
    )
else:
    st.sidebar.success(
        "100%です"
    )

edit_name = st.sidebar.text_input("表示名", value=name)

edit_weekly_goal = st.sidebar.number_input(
    "1週間の目標勉強時間",
    min_value=1.0,
    value=float(weekly_goal),
    step=0.5
)

if st.sidebar.button("プロフィールを保存"):
    upsert_user(
    user_id,
    edit_name,
    edit_weekly_goal,
    prog_ratio,
    math_ratio,
    stat_ratio,
    eng_ratio,
    other_ratio
    )
    st.cache_data.clear()
    st.session_state.notice_message = "プロフィールを保存しました"
    st.session_state.notice_type = "success"
    st.rerun()

default_subjects = default_subjects_map[user_id]

added_subjects = subjects_df[
    subjects_df["user_id"] == user_id
]["subject"].dropna().astype(str).tolist()

user_subjects = []

for subject in default_subjects + added_subjects:
    subject = subject.strip()
    if subject and subject not in user_subjects:
        user_subjects.append(subject)

st.sidebar.divider()
st.sidebar.subheader("科目追加")

new_subject_sidebar = st.sidebar.text_input("追加したい科目")

if st.sidebar.button("科目を追加"):
    if new_subject_sidebar.strip():
        subject_name = new_subject_sidebar.strip()

        if subject_name in user_subjects:
            st.sidebar.warning("その科目は既にあります")
        else:
            append_subject(user_id, subject_name)
            st.cache_data.clear()
            st.session_state.notice_message = "科目を追加しました"
            st.session_state.notice_type = "success"
            st.rerun()
    else:
        st.sidebar.warning("科目名を入力してください")

if st.sidebar.button("💾 理想配分を保存"):

    if ratio_total != 100:

        st.sidebar.error(
            "合計を100%にしてください"
        )

    else:

        upsert_user(
            user_id,
            edit_name,
            edit_weekly_goal,
            prog_ratio,
            math_ratio,
            stat_ratio,
            eng_ratio,
            other_ratio
        )

        st.cache_data.clear()

        st.session_state.notice_message = (
            "理想配分を保存しました"
        )

        st.session_state.notice_type = "success"

        st.rerun()
# =====================
# 集計
# =====================
today = datetime.now(JST).date()
week_start, week_end = get_week_range(today)

user_logs = logs[logs["user_id"] == user_id].copy()

if not user_logs.empty:
    user_logs["date_dt"] = pd.to_datetime(user_logs["date"]).dt.date
    week_logs = user_logs[
        (user_logs["date_dt"] >= week_start) &
        (user_logs["date_dt"] <= week_end)
    ]
else:
    week_logs = pd.DataFrame()

weekly_total = week_logs["hours"].sum() if not week_logs.empty else 0
total_hours = user_logs["hours"].sum() if not user_logs.empty else 0

if not user_logs.empty:
    today_logs = user_logs[user_logs["date_dt"] == today]
else:
    today_logs = pd.DataFrame()

today_total = today_logs["hours"].sum() if not today_logs.empty else 0
remaining = max(edit_weekly_goal - weekly_total, 0)
achievement = min((weekly_total / edit_weekly_goal) * 100, 100)

streak = calc_streak(user_logs)

level, progress_in_level, required_for_level, next_level_total = calc_level(total_hours)
level_progress = progress_in_level / required_for_level
remaining_for_level = next_level_total - total_hours

earned_badges, locked_badges = get_badge_status(
    total_hours,
    streak,
    weekly_total,
    edit_weekly_goal,
    user_logs
)

if remaining == 0:
    mission_text = "🎉 今週の目標達成！今日は復習か軽めの積み上げでOK。"
elif streak == 0:
    mission_text = "🔥 まずは30分だけ記録しよう。ゼロにしないのが勝ち。"
elif achievement >= 70:
    mission_text = "⚔️ あと少し。今日は1時間だけでも積めばかなり強い。"
else:
    mission_text = f"📚 今週の残りは {remaining:.1f}h。今日は1.0hを目標にしよう。"

balance_ratios = {
    "programming": prog_ratio,
    "math": math_ratio,
    "statistics": stat_ratio,
    "english": eng_ratio,
    "other": other_ratio
}

balance_summary = make_balance_summary(
    week_logs,
    edit_weekly_goal,
    balance_ratios
)
# =====================
# ヘッダー
# =====================
st.markdown(
    """
<div class="hero">
<div class="hero-logo-wrap">
<div class="hero-compass">🧭</div>
<div class="hero-logo-text">Study<br>Quest</div>
</div>
</div>
""",
    unsafe_allow_html=True
)

if st.session_state.notice_message:
    if "レベルアップ" in st.session_state.notice_message:
        st.balloons()

    if st.session_state.notice_type == "success":
        st.success(st.session_state.notice_message)
    elif st.session_state.notice_type == "warning":
        st.warning(st.session_state.notice_message)
    else:
        st.info(st.session_state.notice_message)

    st.session_state.notice_message = None

st.markdown(f"""
<div class="mission-card">
    <b>今日のミッション</b><br>
    {mission_text}
</div>
""", unsafe_allow_html=True)


# =====================
# ダッシュボードカード
# =====================
col1, col2 = st.columns(2)

with col1:
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-label">今日</div>
        <div class="stat-number">{today_total:.1f}h</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-label">今週</div>
        <div class="stat-number">{weekly_total:.1f}h</div>
    </div>
    """, unsafe_allow_html=True)

col3, col4 = st.columns(2)

with col3:
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-label">目標まで残り</div>
        <div class="stat-number">{remaining:.1f}h</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-label">連続記録</div>
        <div class="stat-number">{streak}日</div>
    </div>
    """, unsafe_allow_html=True)

col5, col6 = st.columns(2)

with col5:
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-label">レベル</div>
        <div class="stat-number">Lv.{level}</div>
    </div>
    """, unsafe_allow_html=True)

with col6:
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-label">総勉強時間</div>
        <div class="stat-number">{total_hours:.1f}h</div>
    </div>
    """, unsafe_allow_html=True)



# =====================
# 進捗
# =====================
st.markdown('<div class="section-title">進捗</div>', unsafe_allow_html=True)

st.markdown(f"""
<div class="big-progress-card">
    <div class="big-progress-title">今週の達成率</div>
    <div class="big-progress-number">{achievement:.1f}%</div>
    <div class="balance-bar-bg">
        <div class="balance-bar-fill" style="width:{achievement}%;"></div>
    </div>
    <div class="balance-progress-sub">
        {weekly_total:.1f}h / 目標 {edit_weekly_goal:.1f}h
    </div>
</div>
""", unsafe_allow_html=True)


st.markdown('<div class="section-title">🎯 科目バランス</div>', unsafe_allow_html=True)

priority_rows = sorted(
    balance_summary,
    key=lambda x: x["shortage"],
    reverse=True
)

for row in priority_rows:

    if row["ratio"] == 0:
        continue

    title = ""

    if row["achievement"] >= 200:
        title = " 👑"
    elif row["achievement"] >= 150:
        title = " 🚀"

    st.markdown(
        f"#### {row['icon']} {row['label']}　{row['achievement']:.0f}%"
    )

    progress_value = max(
        min(int(row["achievement"]), 100),
        0
    )

    if progress_value > 0:
        st.progress(progress_value)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.caption(f"現在 {row['actual']:.1f}h")

    with col2:
        st.caption(f"目標 {row['target']:.1f}h")

    with col3:
        diff = row["actual"] - row["target"]

        if diff >= 0:
            st.caption(f"超過 +{diff:.1f}h 🚀")
        else:
            st.caption(f"残り {-diff:.1f}h")

    st.markdown("")


st.markdown('<div class="section-title">レベル進捗</div>', unsafe_allow_html=True)

st.markdown(f"""
<div class="big-progress-card">
    <div class="big-progress-title">Lv.{level} → Lv.{level + 1}</div>
    <div class="big-progress-number">{level_progress * 100:.1f}%</div>
    <div class="balance-bar-bg">
        <div class="balance-bar-fill" style="width:{level_progress * 100}%;"></div>
    </div>
    <div class="balance-progress-sub">
        あと {remaining_for_level:.1f} 時間で Lv.{level + 1}
    </div>
</div>
""", unsafe_allow_html=True)

# =====================
# バッジ
# =====================
st.markdown('<div class="section-title">バッジ</div>', unsafe_allow_html=True)

with st.expander(f"🏅 獲得バッジを見る：{len(earned_badges)}個", expanded=True):
    if earned_badges:
        badge_html = ""
        for b in earned_badges:
            badge_html += f'<span class="badge-pill">{b["icon"]} {b["title"]}</span>'

        st.markdown(badge_html, unsafe_allow_html=True)
    else:
        st.write("まだバッジはありません。まずは1時間勉強してみよう。")

with st.expander(f"🔒 未獲得バッジを見る：{len(locked_badges)}個", expanded=False):
    if locked_badges:
        locked_html = ""
        for b in locked_badges:
            locked_html += (
                f'<span class="locked-badge-pill">'
                f'🔒 {b["icon"]} {b["title"]}'
                f'<span class="locked-note">({b["note"]})</span>'
                f'</span>'
            )

        st.markdown(locked_html, unsafe_allow_html=True)
    else:
        st.success("全バッジ獲得済み！すごすぎる。")


# =====================
# 記録エリア
# =====================
st.markdown('<div class="section-title">勉強を記録する</div>', unsafe_allow_html=True)

tab_timer, tab_manual = st.tabs(["⏱️ タイマー学習", "✍️ 手動で記録"])

with tab_timer:
    active_user_sessions = sessions_df[sessions_df["user_id"] == user_id].copy()

    if active_user_sessions.empty:
        st.markdown('<div class="quest-card">', unsafe_allow_html=True)

        with st.form("timer_start_form"):
            timer_subject = st.selectbox(
                "タイマー科目",
                user_subjects,
                key="timer_subject"
            )

            timer_focus = st.slider(
                "予定集中度",
                min_value=0,
                max_value=100,
                value=70,
                key="timer_focus"
            )

            timer_memo = st.text_area(
                "タイマーメモ",
                placeholder="例：民法の復習を開始",
                key="timer_memo"
            )

            start_submitted = st.form_submit_button("▶️ 勉強開始")

            if start_submitted:
                start_session(user_id, timer_subject, timer_focus, timer_memo)
                st.cache_data.clear()
                st.session_state.notice_message = "タイマーを開始しました"
                st.session_state.notice_type = "success"
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    else:
        session_row = active_user_sessions.iloc[0]
        session_index = active_user_sessions.index[0]
        sheet_row = session_index + 2

        start_time = datetime.fromisoformat(str(session_row["start_time"]))

        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=JST)

        elapsed = datetime.now(JST) - start_time
        elapsed_minutes = int(elapsed.total_seconds() // 60)
        elapsed_hours = round(elapsed.total_seconds() / 3600, 2)

        st.markdown(f"""
        <div class="timer-active">
            <b>⏱️ 勉強中</b><br>
            科目：{session_row['subject']}<br>
            開始：{start_time.strftime('%H:%M')}<br>
            経過：約{elapsed_minutes}分
        </div>
        """, unsafe_allow_html=True)

        new_timer_memo = st.text_area(
            "途中メモ",
            value=str(session_row["memo"]),
            placeholder="勉強中に気づいたこと・詰まったところを書く",
            key="active_timer_memo"
        )

        if st.button("📝 メモを保存"):
            update_session_memo_by_sheet_row(sheet_row, new_timer_memo)
            st.cache_data.clear()
            st.session_state.notice_message = "メモを保存しました"
            st.session_state.notice_type = "success"
            st.rerun()

        col_end, col_cancel = st.columns(2)

        with col_end:
            if st.button("⏹️ 終了して記録"):
                if elapsed_hours <= 0:
                    st.warning("記録できる時間が短すぎます")
                else:
                    old_level, _, _, _ = calc_level(total_hours)

                    append_log(
                        user_id,
                        datetime.now(JST).date(),
                        session_row["subject"],
                        elapsed_hours,
                        int(session_row["focus"]),
                        session_row["memo"]
                    )

                    delete_session_by_sheet_row(sheet_row)

                    st.cache_data.clear()

                    new_level, _, _, _ = calc_level(total_hours + elapsed_hours)

                    if new_level > old_level:
                        st.session_state.notice_message = f"🎉 レベルアップ！ Lv.{new_level} になりました！"
                    else:
                        st.session_state.notice_message = f"{elapsed_hours:.2f}時間を記録しました"

                    st.session_state.notice_type = "success"
                    st.rerun()

        with col_cancel:
            if st.button("🗑️ タイマーを取り消す"):
                delete_session_by_sheet_row(sheet_row)
                st.cache_data.clear()
                st.session_state.notice_message = "タイマーを取り消しました"
                st.session_state.notice_type = "success"
                st.rerun()


with tab_manual:
    st.markdown('<div class="quest-card">', unsafe_allow_html=True)

    with st.form("study_form"):
        subject = st.selectbox("科目", user_subjects)

        hours = st.number_input(
            "勉強時間",
            min_value=0.0,
            value=1.0,
            step=0.5
        )

        focus = st.slider(
            "集中度",
            min_value=0,
            max_value=100,
            value=70
        )

        memo = st.text_area(
            "メモ",
            placeholder="例：統計の仮説検定を復習した"
        )

        submitted = st.form_submit_button("記録する")

        if submitted:
            if hours <= 0:
                st.warning("勉強時間を入力してください")
            else:
                old_level, _, _, _ = calc_level(total_hours)

                append_log(
                    user_id,
                    today,
                    subject,
                    hours,
                    focus,
                    memo
                )

                st.cache_data.clear()

                new_level, _, _, _ = calc_level(total_hours + hours)

                if new_level > old_level:
                    st.session_state.notice_message = f"🎉 レベルアップ！ Lv.{new_level} になりました！"
                else:
                    st.session_state.notice_message = "記録しました！"

                st.session_state.notice_type = "success"
                st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


# =====================
# 今週の記録
# =====================
st.markdown('<div class="section-title">今週の記録</div>', unsafe_allow_html=True)

tab_log, tab_subject, tab_focus, tab_delete = st.tabs([
    "📋 記録",
    "📚 科目別",
    "🎯 集中度",
    "🗑️ 削除"
])

with tab_log:
    if week_logs.empty:
        st.write("今週の記録はまだありません。")
    else:
        display_logs = week_logs[
            ["date", "subject", "hours", "focus", "memo"]
        ].copy()

        display_logs = display_logs.sort_values("date", ascending=False)

        for _, row in display_logs.iterrows():
            memo_text = str(row["memo"]).strip()
            if memo_text == "" or memo_text == "nan":
                memo_text = "メモなし"

            st.markdown(f"""
            <div class="record-card">
                <div class="record-top">
                    <div class="record-subject">{row["subject"]}</div>
                    <div class="record-date">{row["date"]}</div>
                </div>
                <div class="record-meta">
                    <span class="record-chip">⏱️ {float(row["hours"]):.2f}h</span>
                    <span class="record-chip">🎯 集中 {int(float(row["focus"]))}%</span>
                    <span class="record-chip">📝 {memo_text}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)


with tab_subject:
    if week_logs.empty:
        st.write("科目別に表示できる記録がまだありません。")
    else:
        subject_summary = (
            week_logs
            .groupby("subject")["hours"]
            .sum()
            .reset_index()
            .sort_values("hours", ascending=False)
        )

        total_week_hours = subject_summary["hours"].sum()

        st.caption("※ 進捗バーではなく、今週の勉強時間ランキングとして表示しています。")

        for rank, (_, row) in enumerate(subject_summary.iterrows(), start=1):
            subject_name = row["subject"]
            hours_value = float(row["hours"])
            share = 0 if total_week_hours == 0 else hours_value / total_week_hours * 100

            if rank == 1:
                icon = "🥇"
            elif rank == 2:
                icon = "🥈"
            elif rank == 3:
                icon = "🥉"
            else:
                icon = f"{rank}"

            st.markdown(f"""
            <div class="study-rank-card">
                <div class="rank-row">
                    <div class="rank-badge">{icon}</div>
                    <div>
                        <div class="rank-title">{subject_name}</div>
                        <div class="rank-sub">今週の割合：{share:.1f}%</div>
                    </div>
                    <div class="rank-value">{hours_value:.1f}h</div>
                </div>
            </div>
            """, unsafe_allow_html=True)


with tab_focus:
    if week_logs.empty:
        st.write("集中度を表示できる記録がまだありません。")
    else:
        focus_summary = (
            week_logs
            .groupby("subject")["focus"]
            .mean()
            .reset_index()
            .sort_values("focus", ascending=False)
        )

        st.caption("※ 科目ごとの平均集中度です。")

        for rank, (_, row) in enumerate(focus_summary.iterrows(), start=1):
            subject_name = row["subject"]
            focus_value = float(row["focus"])

            if focus_value >= 80:
                comment = "かなり集中できてる"
                focus_class = "focus-good"
            elif focus_value >= 60:
                comment = "安定している"
                focus_class = "focus-mid"
            else:
                comment = "少し疲れ気味かも"
                focus_class = "focus-low"

            st.markdown(f"""
            <div class="study-rank-card">
                <div class="rank-row">
                    <div class="rank-badge">🎯</div>
                    <div>
                        <div class="rank-title">{subject_name}</div>
                        <div class="rank-sub">{comment}</div>
                    </div>
                    <div class="rank-value {focus_class}">{focus_value:.1f}%</div>
                </div>
            </div>
            """, unsafe_allow_html=True)


with tab_delete:
    if week_logs.empty:
        st.write("削除できる今週の記録はありません。")
    else:
        user_week_logs = logs[logs["user_id"] == user_id].copy()

        user_week_logs["date_dt"] = pd.to_datetime(
            user_week_logs["date"]
        ).dt.date

        user_week_logs = user_week_logs[
            (user_week_logs["date_dt"] >= week_start) &
            (user_week_logs["date_dt"] <= week_end)
        ]

        delete_options = []

        for idx, row in user_week_logs.iterrows():
            sheet_row = idx + 2
            label = (
                f"{row['date']} | "
                f"{row['subject']} | "
                f"{row['hours']}h | "
                f"集中{row['focus']}%"
            )

            delete_options.append((sheet_row, label))

        if delete_options:
            selected_delete = st.selectbox(
                "削除する記録を選択",
                delete_options,
                format_func=lambda x: x[1]
            )

            if st.button("この記録を削除"):
                delete_log_by_sheet_row(selected_delete[0])

                st.cache_data.clear()

                st.session_state.notice_message = "記録を削除しました"
                st.session_state.notice_type = "success"
                st.rerun()

st.markdown('<div class="section-title">🌙 明日やりたいこと</div>', unsafe_allow_html=True)

with st.form("tomorrow_note_form"):
    tomorrow_note = st.text_area(
        "できたら明日やりたいこと",
        placeholder="例：統計の復習を30分だけ / 英単語を少し見る"
    )

    submitted_tomorrow_note = st.form_submit_button("ゆるくメモする")

    if submitted_tomorrow_note:
        if tomorrow_note.strip():
            append_tomorrow_note(user_id, tomorrow_note.strip())
            st.cache_data.clear()
            st.session_state.notice_message = "明日やりたいことをメモしました"
            st.session_state.notice_type = "success"
            st.rerun()
        else:
            st.warning("内容を入力してね")
