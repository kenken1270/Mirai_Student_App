# Supabase の plans テーブルに deadline / month_plan / task_type 等のカラムを追加してください（未作成だと INSERT が失敗することがあります）。
# 例: ALTER TABLE plans ADD COLUMN IF NOT EXISTS deadline text;
#     ALTER TABLE plans ADD COLUMN IF NOT EXISTS month_plan text;
#     ALTER TABLE plans ADD COLUMN IF NOT EXISTS task_type text DEFAULT 'lesson';

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import random
import re
import json
import time
from datetime import date, datetime, timedelta
import calendar
import os
from supabase import create_client, Client

try:
    from streamlit_calendar import calendar as st_calendar
    CALENDAR_AVAILABLE = True
except ImportError:
    CALENDAR_AVAILABLE = False

try:
    from streamlit_option_menu import option_menu
    HAS_OPTION_MENU = True
except ImportError:
    HAS_OPTION_MENU = False

import base64
from pathlib import Path


def get_logo_base64() -> str:
    """ロゴ画像をbase64エンコードして返す"""
    logo_path = Path("assets/logo.png")
    if logo_path.exists():
        with open(logo_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""


LOGO_B64 = get_logo_base64()


def logo_img(width: int = 80) -> str:
    """ロゴのHTMLタグを返す（base64埋め込み）"""
    if LOGO_B64:
        return (
            f'<img src="data:image/png;base64,{LOGO_B64}" '
            f'width="{width}" style="vertical-align:middle;">'
        )
    return "📚"


st.set_page_config(
    page_title="未来塾 生徒用アプリ",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

ADMIN_OPTION = "👨‍🏫 管理者"
ADMIN_PASSWORD = "admin"
STUDENT_PASSWORD = "mirai2026"
LANG_JA = "ja"
LANG_ZH = "zh"
COL_LAST_LOGIN = "last_login_date"
COL_LAST_VISIT = "last_visit_date"
COL_STREAK = "streak"
COL_RECENT_LOGINS = "recent_login_dates"
GACHA_COST = 50
TASK_TOGGLE_POINTS = 10

PAGE_HOME = "home"
PAGE_STUDY = "study"
PAGE_TEST = "test"
PAGE_GACHA = "gacha"
PAGE_SCHEDULE = "schedule"
PAGE_PLAN = "plan"

NAV_OPTIONS = ["ホーム", "📅 今日の学習", "計画確認", "小テスト", "ガチャ"]
NAV_ICONS = ["house", "journal-check", "map", "pencil-square", "gift"]
OPTION_TO_PAGE = {
    "ホーム": PAGE_HOME, "📅 今日の学習": PAGE_SCHEDULE, "計画確認": PAGE_PLAN,
    "小テスト": PAGE_TEST, "ガチャ": PAGE_GACHA,
}
PAGE_TO_OPTION = {
    PAGE_HOME: "ホーム", PAGE_SCHEDULE: "📅 今日の学習", PAGE_PLAN: "計画確認",
    PAGE_STUDY: "📅 今日の学習", PAGE_TEST: "小テスト", PAGE_GACHA: "ガチャ",
}

TEXTS = {
    "ja": {
        "school_name": "未来塾",
        "catchcopy": "楽しく学んで、未来を切り開こう！",
        "select_name": "名前を選んでください",
        "password": "パスワード",
        "login_btn": "ログイン",
        "login_error": "パスワードが違います",
        "news_title": "📢 お知らせ",
        "lang_btn": "中文",
        "logout_btn": "ログアウト",
        "nav_home": "ホーム",
        "nav_study": "📅 今日の学習",
        "nav_plan": "計画確認",
        "nav_test": "小テスト",
        "nav_gacha": "ガチャ",
        "streak": "連続",
        "streak_unit": "日目！",
        "mood": "今日の気分は？",
        "mood_good": "元気！",
        "mood_normal": "ふつう",
        "mood_sleepy": "眠い...",
        "admin": "👨‍🏫 管理者",
    },
    "zh": {
        "school_name": "未来塾",
        "catchcopy": "快乐学习，开创未来！",
        "select_name": "请选择姓名",
        "password": "密码",
        "login_btn": "登录",
        "login_error": "密码错误",
        "news_title": "📢 通知",
        "lang_btn": "日本語",
        "logout_btn": "退出登录",
        "nav_home": "主页",
        "nav_study": "📅 今日的学习",
        "nav_plan": "计划确认",
        "nav_test": "小测验",
        "nav_gacha": "扭蛋机",
        "streak": "连续",
        "streak_unit": "天！",
        "mood": "今天心情怎么样？",
        "mood_good": "很好！",
        "mood_normal": "一般",
        "mood_sleepy": "犯困...",
        "admin": "👨‍🏫 管理员",
    },
}

# ==========================================================
# ▼ Supabase 接続
# ==========================================================
@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)


@st.cache_data(ttl=30)
def load_events(username: str) -> pd.DataFrame:
    sb = get_supabase()
    res = sb.table("events").select("*").eq("username", username).execute()
    df = pd.DataFrame(res.data) if res.data else pd.DataFrame(
        columns=["id", "username", "event_name", "event_date", "event_type", "note"]
    )
    for col, default in [("event_type", "exam"), ("note", "")]:
        if col not in df.columns:
            df[col] = default
    return df


def insert_event(username, event_name, event_date, event_type="exam", note=""):
    sb = get_supabase()
    sb.table("events").insert({
        "username": username,
        "event_name": event_name,
        "event_date": event_date,
        "event_type": event_type,
        "note": note,
    }).execute()
    st.cache_data.clear()


def delete_event(event_id):
    sb = get_supabase()
    sb.table("events").delete().eq("id", event_id).execute()
    st.cache_data.clear()


@st.cache_data(ttl=60)
def load_master_events() -> pd.DataFrame:
    sb = get_supabase()
    res = (
        sb.table("master_events")
        .select("*")
        .eq("is_active", True)
        .order("event_date")
        .execute()
    )
    return pd.DataFrame(res.data) if res.data else pd.DataFrame(
        columns=["id", "event_name", "event_date", "event_type", "note", "is_active"]
    )


def bulk_insert_events_to_all_users(master_event_ids: list):
    """指定したmaster_eventsを全生徒に一括配布"""
    sb = get_supabase()
    df_users = load_users()
    df_master = load_master_events()

    for _, user_row in df_users.iterrows():
        username = (
            user_row["username"]
            if "username" in user_row.index
            else user_row["ユーザー名"]
        )
        if username == ADMIN_OPTION:
            continue
        for mid in master_event_ids:
            ev = df_master[df_master["id"] == mid]
            if len(ev) == 0:
                continue
            ev = ev.iloc[0]
            # 既に同じイベントが登録済みでないか確認
            existing = (
                sb.table("events")
                .select("id")
                .eq("username", username)
                .eq("event_name", str(ev["event_name"]))
                .eq("event_date", str(ev["event_date"])[:10])
                .execute()
            )
            if not existing.data:
                sb.table("events").insert({
                    "username": username,
                    "event_name": str(ev["event_name"]),
                    "event_date": str(ev["event_date"])[:10],
                    "event_type": str(ev.get("event_type", "exam")),
                    "note": str(ev.get("note", "")),
                }).execute()
    st.cache_data.clear()


def today_str():
    return date.today().isoformat()

def this_month_str():
    return date.today().strftime("%Y-%m")

# ==========================================================
# ▼ ユーザーデータ
# ==========================================================
@st.cache_data(ttl=30)
def load_users() -> pd.DataFrame:
    sb = get_supabase()
    res = sb.table("users").select("*").execute()
    if res.data:
        df = pd.DataFrame(res.data)
    else:
        df = pd.DataFrame(columns=["id", "username", "current_points",
                                   COL_LAST_LOGIN, COL_STREAK, COL_LAST_VISIT, COL_RECENT_LOGINS])
    for col, default in [(COL_LAST_LOGIN, ""), (COL_STREAK, 0),
                         (COL_LAST_VISIT, ""), (COL_RECENT_LOGINS, ""), ("current_points", 0)]:
        if col not in df.columns:
            df[col] = default
    return df

def save_user_fields(username: str, update_dict: dict):
    sb = get_supabase()
    sb.table("users").update(update_dict).eq("username", username).execute()
    st.cache_data.clear()

def create_user_if_not_exists(username: str):
    sb = get_supabase()
    res = sb.table("users").select("id").eq("username", username).execute()
    if not res.data:
        sb.table("users").insert({"username": username, "current_points": 0}).execute()
        st.cache_data.clear()

# ==========================================================
# ▼ 計画データ
# ==========================================================
@st.cache_data(ttl=30)
def load_plans() -> pd.DataFrame:
    sb = get_supabase()
    res = sb.table("plans").select("*").execute()
    if res.data:
        df = pd.DataFrame(res.data)
    else:
        df = pd.DataFrame(columns=["id", "username", "big_plan", "mid_plan",
                                   "task_name", "task_date", "is_done",
                                   "video_url", "material_id", "page_range",
                                   "deadline", "month_plan", "task_type"])
    # 旧カラム名との互換マッピング
    rename_map = {
        "username": "ユーザー名", "big_plan": "大計画", "mid_plan": "中計画",
        "task_name": "小計画タスク", "task_date": "日付", "is_done": "完了フラグ",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    for col, default in [
        ("deadline", ""),
        ("month_plan", ""),
        ("video_url", ""),
        ("material_id", ""),
        ("page_range", ""),
        ("完了フラグ", 0),
        ("task_type", "lesson"),
    ]:
        if col not in df.columns:
            df[col] = default
    return df

def update_plan_row(plan_id: int, update_dict: dict):
    """Supabaseのカラム名でupdateする"""
    sb = get_supabase()
    sb.table("plans").update(update_dict).eq("id", plan_id).execute()
    st.cache_data.clear()

def insert_plan_row(
    username: str,
    big_plan: str,
    mid_plan: str,
    task_name: str,
    task_date: str,
    video_url: str = "",
    material_id: str = "",
    page_range: str = "",
    deadline: str = "",
    month_plan: str = "",
    task_type: str = "lesson",
):
    sb = get_supabase()
    sb.table("plans").insert({
        "username": username,
        "big_plan": big_plan,
        "mid_plan": mid_plan,
        "task_name": task_name,
        "task_date": task_date,
        "is_done": 0,
        "video_url": video_url or "",
        "material_id": str(material_id) if material_id else "",
        "page_range": page_range or "",
        "deadline": deadline or "",
        "month_plan": month_plan or "",
        "task_type": task_type or "lesson",
    }).execute()
    st.cache_data.clear()

def delete_plan_row(plan_id: int):
    sb = get_supabase()
    sb.table("plans").delete().eq("id", plan_id).execute()
    st.cache_data.clear()


def delete_plans_by_condition(
    username: str, big_plan=None, mid_plan=None
):
    """大計画名または中計画名に一致する全行を削除"""
    sb = get_supabase()
    q = sb.table("plans").delete().eq("username", username)
    if big_plan is not None:
        q = q.eq("big_plan", big_plan)
    if mid_plan is not None:
        q = q.eq("mid_plan", mid_plan)
    q.execute()
    st.cache_data.clear()


# ==========================================================
# ▼ コンテンツデータ
# ==========================================================
@st.cache_data(ttl=60)
def load_content() -> pd.DataFrame:
    sb = get_supabase()
    res = sb.table("content").select("*").execute()
    if res.data:
        df = pd.DataFrame(res.data)
    else:
        df = pd.DataFrame(columns=["id", "subject", "content_type", "title", "url"])
    rename_map = {"subject": "教科", "content_type": "種別", "title": "タイトル", "url": "URL"}
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    return df

def insert_content_row(subject: str, content_type: str, title: str, url: str):
    sb = get_supabase()
    sb.table("content").insert({
        "subject": subject, "content_type": content_type, "title": title, "url": url
    }).execute()
    st.cache_data.clear()

def update_content_row(content_id: int, update_dict: dict):
    sb = get_supabase()
    sb.table("content").update(update_dict).eq("id", content_id).execute()
    st.cache_data.clear()

def delete_content_row(content_id: int):
    sb = get_supabase()
    sb.table("content").delete().eq("id", content_id).execute()
    st.cache_data.clear()

# ==========================================================
# ▼ お知らせデータ
# ==========================================================
@st.cache_data(ttl=60)
def load_news() -> pd.DataFrame:
    sb = get_supabase()
    res = sb.table("news").select("*").execute()
    if res.data:
        df = pd.DataFrame(res.data)
    else:
        df = pd.DataFrame(columns=["id", "message", "created_date", "target_user"])
    rename_map = {"message": "メッセージ", "created_date": "作成日"}
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    if "target_user" not in df.columns:
        df["target_user"] = "全員"
    return df

def insert_news_row(message: str, created_date: str, target_user: str):
    sb = get_supabase()
    sb.table("news").insert({
        "message": message, "created_date": created_date, "target_user": target_user
    }).execute()
    st.cache_data.clear()

def delete_news_row(news_id: int):
    sb = get_supabase()
    sb.table("news").delete().eq("id", news_id).execute()
    st.cache_data.clear()

# ==========================================================
# ▼ 教材データ
# ==========================================================
@st.cache_data(ttl=60)
def load_materials() -> pd.DataFrame:
    sb = get_supabase()
    res = sb.table("materials").select("*").execute()
    if res.data:
        df = pd.DataFrame(res.data)
    else:
        df = pd.DataFrame(columns=["id", "subject", "material_name",
                                   "publisher", "grade", "toc_data"])
    rename_map = {
        "subject": "教科", "material_name": "教材名", "publisher": "出版社",
        "grade": "対象学年", "toc_data": "目次データ"
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    if "ID" not in df.columns and "id" in df.columns:
        df["ID"] = df["id"]
    return df

def insert_material_row(subject: str, material_name: str, publisher: str,
                        grade: str, toc_data: str):
    sb = get_supabase()
    sb.table("materials").insert({
        "subject": subject, "material_name": material_name, "publisher": publisher,
        "grade": grade, "toc_data": toc_data,
    }).execute()
    st.cache_data.clear()

# ==========================================================
# ▼ ダイアログ
# ==========================================================
@st.dialog("タスクの編集")
def edit_task_dialog(plan_id):
    df = load_plans()
    df["日付"] = df["日付"].astype(str).str[:10]
    row_df = df[df["id"] == plan_id]
    if row_df.empty:
        st.warning("タスクが見つかりません。")
        return
    row = row_df.iloc[0]
    st.caption(f"科目（中計画）：{row['中計画']}　ステータス：{'完了' if int(row['完了フラグ']) == 1 else '未完了'}")
    try:
        current_d = datetime.strptime(str(row["日付"])[:10], "%Y-%m-%d").date()
    except Exception:
        current_d = date.today()
    new_date = st.date_input("日付", value=current_d, key="dialog_edit_date")
    new_task_name = st.text_input("タスク名", value=str(row["小計画タスク"]), key="dialog_edit_task")
    col_s, col_d, col_c = st.columns(3)
    with col_s:
        if st.button("保存（更新）", key="dialog_edit_save"):
            update_dict = {}
            if new_task_name.strip():
                update_dict["task_name"] = new_task_name.strip()
            update_dict["task_date"] = new_date.isoformat()
            update_plan_row(int(row["id"]), update_dict)
            st.rerun()
    with col_d:
        if st.button("削除", key="dialog_edit_delete"):
            delete_plan_row(int(row["id"]))
            st.rerun()
    with col_c:
        if st.button("キャンセル", key="dialog_edit_cancel"):
            st.rerun()

@st.dialog("新規タスク追加")
def add_task_dialog(mid_plan, selected_user):
    df = load_plans()
    user_rows = df[df["ユーザー名"] == selected_user]
    big_plan = user_rows["大計画"].iloc[0] if len(user_rows) > 0 else ""
    st.markdown(f"**中計画：** {mid_plan}")
    new_task_name = st.text_input("何をするか（タスク名）", key="dialog_add_task")
    new_task_date = st.date_input("いつやるか（日付）", value=date.today(), key="dialog_add_date")
    col_a, col_c = st.columns(2)
    with col_a:
        if st.button("追加する", key="dialog_add_submit"):
            if new_task_name and new_task_name.strip():
                insert_plan_row(
                    username=selected_user,
                    big_plan=big_plan,
                    mid_plan=mid_plan,
                    task_name=new_task_name.strip(),
                    task_date=new_task_date.isoformat(),
                )
                st.rerun()
            else:
                st.warning("タスク名を入力してください。")
    with col_c:
        if st.button("キャンセル", key="dialog_add_cancel"):
            st.rerun()

# ==========================================================
# ▼ セッション状態初期化
# ==========================================================
if "page" not in st.session_state:
    st.session_state.page = PAGE_HOME
if "toast_shown" not in st.session_state:
    st.session_state.toast_shown = False
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "lang" not in st.session_state:
    st.session_state.lang = "ja"
if "login_user" not in st.session_state:
    st.session_state.login_user = ""
if "plan_mode" not in st.session_state:
    st.session_state.plan_mode = None


def show_top_page():
    lang = st.session_state.lang
    t = TEXTS[lang]

    _, col_lang = st.columns([4, 1])
    with col_lang:
        if st.button(t["lang_btn"], key="lang_toggle"):
            st.session_state.lang = LANG_ZH if lang == LANG_JA else LANG_JA
            st.rerun()

    # ロゴ＋塾名をセンタリング表示
    _logo_top = (
        f'<img src="data:image/png;base64,{LOGO_B64}" width="140" '
        f'style="margin-bottom:12px;">'
        if LOGO_B64
        else '<div style="font-size:4rem;margin-bottom:12px;">📚</div>'
    )
    st.markdown(
        f"""
    <div style="text-align:center;padding:20px 0 10px 0;">
        {_logo_top}
        <h1 style="color:#F0C040;margin:0;font-size:2em;">未来塾</h1>
        <p style="color:#636e72;font-size:1em;margin:4px 0 0 0;">
            MIRAI JAPANESE LANGUAGE SCHOOL
        </p>
        <p style="color:#2d3436;font-size:1.1em;margin:12px 0;">
            楽しく学んで、未来を切り開こう！
        </p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.markdown("---")

    df_news = load_news()
    if "target_user" not in df_news.columns:
        df_news["target_user"] = "全員"
    news_all = df_news[df_news["target_user"] == "全員"]
    if len(news_all) > 0:
        st.markdown(f"### {t['news_title']}")
        for _, row in news_all.iterrows():
            st.warning("⚠️ " + str(row.get("メッセージ", "")), icon="📢")
        st.markdown("---")

    st.markdown("""
    <div style="max-width: 400px; margin: 0 auto;">
        <h2 style="text-align:center; color: #f9a825;">🔐 Login</h2>
    </div>
    """, unsafe_allow_html=True)

    df_u = load_users()
    username_col = "username" if "username" in df_u.columns else "ユーザー名"
    user_list = df_u[username_col].tolist()

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        selected = st.selectbox(t["select_name"], user_list, key="top_user_select")
        password = st.text_input(t["password"], type="password", key="top_password")
        if st.button(t["login_btn"], type="primary", use_container_width=True, key="top_login_btn"):
            if password == STUDENT_PASSWORD:
                st.session_state.logged_in = True
                st.session_state.login_user = selected
                st.session_state.page = PAGE_HOME
                st.rerun()
            else:
                st.error(t["login_error"])

        st.markdown("---")
        if st.button("👨‍🏫 管理者ログイン", key="admin_login_top"):
            st.session_state.logged_in = True
            st.session_state.login_user = ADMIN_OPTION
            st.rerun()


# ==========================================================
# ▼ 共通データ読み込み
# ==========================================================
if not st.session_state.logged_in:
    show_top_page()
    st.stop()

selected_user = st.session_state.login_user

st.markdown("""
<style>
    [data-testid="stSidebar"] { display: none; }
    [data-testid="collapsedControl"] { display: none; }
</style>
""", unsafe_allow_html=True)

if st.session_state.login_user == ADMIN_OPTION:
    if "admin_ok" not in st.session_state:
        st.session_state.admin_ok = False
    if not st.session_state.admin_ok:
        st.title("👨‍🏫 管理者ログイン")
        pwd = st.text_input("パスワード", type="password", key="admin_pwd_top")
        if st.button("ログイン", key="admin_login_btn"):
            if pwd == ADMIN_PASSWORD:
                st.session_state.admin_ok = True
                st.rerun()
            else:
                st.error("パスワードが違います")
        if st.button("← トップに戻る", key="back_to_top"):
            st.session_state.logged_in = False
            st.session_state.login_user = ""
            st.session_state.admin_ok = False
            st.rerun()
        st.stop()

df = load_users()
df_plans = load_plans()

# st.sidebar.title("👤 ユーザー選択")
# st.sidebar.markdown("---")
# user_names = df["username"].tolist() if "username" in df.columns else df["ユーザー名"].tolist()
# options = user_names + [ADMIN_OPTION]
# _sidebar_idx = 0
# if st.session_state.login_user and st.session_state.login_user in options:
#     _sidebar_idx = options.index(st.session_state.login_user)
# selected_user = st.sidebar.selectbox("名前を選んでください", options=options, index=_sidebar_idx)

# ==========================================================
# ▼ 管理者画面
# ==========================================================
if selected_user == ADMIN_OPTION:
    col_admin_logo, col_admin_title, col_admin_logout = st.columns([1, 7, 1])
    with col_admin_logo:
        if LOGO_B64:
            st.markdown(
                f'<img src="data:image/png;base64,{LOGO_B64}" '
                f'width="50" style="margin-top:4px;">',
                unsafe_allow_html=True,
            )
    with col_admin_title:
        st.markdown("## 🏫 管理者画面")
    with col_admin_logout:
        if st.button("🚪 ログアウト", key="admin_logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.login_user = ""
            st.session_state.admin_ok = False
            st.session_state.page = PAGE_HOME
            st.rerun()

    tab_dash, tab_content, tab_materials, tab_news, tab5 = st.tabs(
        [
            "📊 生徒の進捗一覧",
            "📎 教材管理",
            "📚 教材マスター",
            "📢 お知らせ管理",
            "📅 イベント一括配布",
        ]
    )

    with tab_dash:
        st.subheader("生徒の進捗ダッシュボード")
        df_u = load_users()
        username_col = "username" if "username" in df_u.columns else "ユーザー名"
        pts_col = "current_points" if "current_points" in df_u.columns else "現在ポイント"
        dash = df_u[[username_col, pts_col, COL_STREAK, COL_LAST_VISIT]].copy()
        dash.columns = ["生徒名", "ポイント", "連続ログイン日数", "最終ログイン日"]
        dash["最終ログイン日"] = dash["最終ログイン日"].fillna("").astype(str)
        cutoff = (date.today() - timedelta(days=3)).isoformat()
        def highlight_old(row):
            v = str(row["最終ログイン日"]).strip()
            if not v or v == "nan":
                return ["background-color: #ffcccc"] * len(row)
            if v < cutoff:
                return ["background-color: #ffcccc"] * len(row)
            return [""] * len(row)
        st.dataframe(dash.style.apply(highlight_old, axis=1), use_container_width=True, hide_index=True)
        st.caption("※ 赤背景＝最終ログインが3日以上前（要注意）")

    with tab_content:
        st.subheader("教材（動画・小テスト）URL 管理")
        df_c = load_content()
        subject_col = "教科" if "教科" in df_c.columns else "subject"
        for subject in ["国語", "算数", "理科", "社会"]:
            with st.expander(f"📚 {subject}", expanded=True):
                sub = df_c[df_c[subject_col] == subject] if len(df_c) else pd.DataFrame()
                for _, row in sub.iterrows():
                    c1, c2 = st.columns([4, 1])
                    title_val = row.get("タイトル", row.get("title", ""))
                    type_val = row.get("種別", row.get("content_type", ""))
                    url_val = str(row.get("URL", row.get("url", "")))
                    url_preview = url_val[:60] + ("..." if len(url_val) > 60 else "")
                    row_id = int(row["id"])
                    with c1:
                        st.markdown(f"**{title_val}**（{type_val}）　{url_preview}")
                    with c2:
                        if st.button("削除", key=f"content_del_{row_id}"):
                            delete_content_row(row_id)
                            st.rerun()
                        if st.button("編集", key=f"content_edit_{row_id}"):
                            st.session_state[f"content_editing_{subject}"] = row_id
                            st.rerun()
                adding = st.session_state.get(f"content_adding_{subject}")
                editing_id = st.session_state.get(f"content_editing_{subject}")
                show_form = adding or (editing_id is not None)
                if show_form:
                    df_c2 = load_content()
                    if editing_id is not None:
                        edit_row_df = df_c2[df_c2["id"] == editing_id]
                        if not edit_row_df.empty:
                            erow = edit_row_df.iloc[0]
                            default_tit = erow.get("タイトル", erow.get("title", ""))
                            default_typ = erow.get("種別", erow.get("content_type", "動画"))
                            default_url = erow.get("URL", erow.get("url", ""))
                        else:
                            default_tit = default_url = ""; default_typ = "動画"
                    else:
                        default_tit = default_url = ""; default_typ = "動画"
                    form_suffix = f"edit_{editing_id}" if editing_id else "new"
                    tit = st.text_input("タイトル", value=default_tit, key=f"ctitle_{subject}_{form_suffix}")
                    typ = st.selectbox("種別", ["動画", "小テスト"],
                                       index=0 if default_typ == "動画" else 1,
                                       key=f"ctype_{subject}_{form_suffix}")
                    url = st.text_input("小テストURL" if typ == "小テスト" else "動画URL",
                                        value=default_url, key=f"curl_{subject}_{form_suffix}")
                    if st.button("保存", key=f"csave_{subject}") and tit and url:
                        if editing_id:
                            update_content_row(editing_id, {
                                "title": tit, "content_type": typ, "url": url
                            })
                        else:
                            insert_content_row(subject, typ, tit, url)
                        st.session_state[f"content_adding_{subject}"] = False
                        st.session_state[f"content_editing_{subject}"] = None
                        st.rerun()
                    if st.button("キャンセル", key=f"ccancel_{subject}"):
                        st.session_state[f"content_adding_{subject}"] = False
                        st.session_state[f"content_editing_{subject}"] = None
                        st.rerun()
                if not show_form and st.button(f"➕ 追加", key=f"content_add_{subject}"):
                    st.session_state[f"content_adding_{subject}"] = True
                    st.rerun()

    with tab_materials:
        st.subheader("📚 教材マスター登録")
        if "materials_toc_draft" not in st.session_state:
            st.session_state.materials_toc_draft = []
        st.markdown("**教材の基本情報**")
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            mat_kyouka = st.selectbox("教科", ["国語", "算数", "理科", "社会"], key="mat_kyouka")
            mat_name = st.text_input("教材名", key="mat_name")
        with col_m2:
            mat_pub = st.text_input("出版社", key="mat_pub")
            mat_grade = st.text_input("対象学年（例: 中1・小5）", key="mat_grade")
        st.markdown("---")
        st.markdown("**目次・単元の登録**")
        col_t1, col_t2, col_t3 = st.columns([2, 2, 1])
        with col_t1:
            toc_unit = st.text_input("単元名", key="toc_unit")
        with col_t2:
            toc_pages = st.text_input("ページ範囲（例: P.10-15）", key="toc_pages")
        with col_t3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("➕ 追加", key="toc_add_btn") and toc_unit.strip():
                st.session_state.materials_toc_draft.append(
                    {"単元名": toc_unit.strip(), "ページ範囲": toc_pages.strip() or "-"}
                )
                st.rerun()
        if st.session_state.materials_toc_draft:
            st.markdown("**一時保存中の目次**")
            for i, item in enumerate(st.session_state.materials_toc_draft):
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(f"- **{item['単元名']}** … {item['ページ範囲']}")
                with c2:
                    if st.button("削除", key=f"toc_del_{i}"):
                        st.session_state.materials_toc_draft.pop(i)
                        st.rerun()
            if st.button("教材を保存", type="primary", key="mat_save_btn"):
                if not mat_name.strip():
                    st.warning("教材名を入力してください。")
                else:
                    toc_json = json.dumps(st.session_state.materials_toc_draft, ensure_ascii=False)
                    insert_material_row(mat_kyouka, mat_name.strip(), mat_pub.strip(),
                                        mat_grade.strip(), toc_json)
                    st.session_state.materials_toc_draft = []
                    st.success("教材を保存しました。")
                    st.rerun()
        else:
            st.caption("単元名とページ範囲を入力して「追加」を押すと、ここに目次が溜まります。")
        st.markdown("---")
        st.subheader("登録済み教材一覧")
        df_m = load_materials()
        if len(df_m) == 0:
            st.info("まだ教材が登録されていません。")
        else:
            id_col = "ID" if "ID" in df_m.columns else "id"
            df_display = df_m[[id_col, "教科", "教材名", "出版社", "対象学年"]].copy()
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            st.markdown("**詳細（目次）を表示**")
            mat_options = [f"ID{row[id_col]} {row['教材名']}（{row['教科']}）" for _, row in df_m.iterrows()]
            sel_idx = st.selectbox("教材を選択", range(len(mat_options)),
                                   format_func=lambda i: mat_options[i], key="mat_sel_detail")
            if sel_idx is not None and 0 <= sel_idx < len(df_m):
                toc_str = df_m.iloc[sel_idx].get("目次データ", "[]")
                try:
                    toc_list = json.loads(toc_str) if isinstance(toc_str, str) else toc_str
                except Exception:
                    toc_list = []
                for item in toc_list:
                    st.markdown(f"- **{item.get('単元名', '')}** … {item.get('ページ範囲', '')}")

    with tab_news:
        st.subheader("お知らせメッセージ（ホームに表示）")
        df_n = load_news()
        all_usernames = load_users()
        un_col = "username" if "username" in all_usernames.columns else "ユーザー名"
        unames = all_usernames[un_col].tolist()
        for _, row in df_n.iterrows():
            c1, c2 = st.columns([4, 1])
            news_id = int(row["id"])
            with c1:
                target = row.get("target_user", "全員")
                st.markdown(f"- **[{target}]** {row.get('メッセージ', '')}")
            with c2:
                if st.button("削除", key=f"news_del_{news_id}"):
                    delete_news_row(news_id)
                    st.rerun()
        if st.button("➕ お知らせを追加", key="news_add_btn"):
            st.session_state["news_adding"] = True
        if st.session_state.get("news_adding"):
            msg = st.text_area("メッセージ", key="new_news_msg")
            target_options = ["全員"] + unames
            target_user = st.selectbox("対象（全員 / 生徒名）", options=target_options, key="news_target_user")
            if st.button("登録", key="news_save_btn") and msg.strip():
                insert_news_row(msg.strip(), today_str(), target_user)
                st.session_state["news_adding"] = False
                st.rerun()
            if st.button("キャンセル", key="news_cancel_btn"):
                st.session_state["news_adding"] = False
                st.rerun()

    with tab5:
        st.markdown("### 📅 英検・漢検 日程一括配布")
        st.info(
            "チェックを入れたイベントを全生徒のカレンダーに一括登録します。"
            "不要なイベントは各生徒が自分で削除できます。"
        )

        df_master = load_master_events()

        if df_master.empty:
            st.warning(
                "マスターイベントが登録されていません。"
                "Supabaseのmaster_eventsテーブルを確認してください。"
            )
        else:
            EVENT_TYPE_LABEL = {
                "exam": "📝 試験・検定日",
                "deadline": "⏰ 申込締切日",
                "event": "🎉 行事・イベント",
                "other": "📌 その他",
            }

            selected_ids = []

            for etype, group_df in df_master.groupby("event_type"):
                st.markdown(f"**{EVENT_TYPE_LABEL.get(etype, etype)}**")
                for _, ev_row in group_df.iterrows():
                    ev_id = int(ev_row["id"])
                    ev_date = str(ev_row["event_date"])[:10]
                    ev_note = str(ev_row.get("note", ""))
                    label = f"{ev_date}　{ev_row['event_name']}"
                    if ev_note and ev_note != "nan":
                        label += f"　({ev_note})"
                    checked = st.checkbox(
                        label, value=True, key=f"master_ev_{ev_id}"
                    )
                    if checked:
                        selected_ids.append(ev_id)

            st.markdown("---")
            col_bulk1, col_bulk2 = st.columns([3, 1])
            with col_bulk1:
                st.markdown(
                    f"選択中：**{len(selected_ids)}件** のイベントを全生徒に配布します"
                )
            with col_bulk2:
                if st.button(
                    "🚀 全生徒に一括配布",
                    type="primary",
                    use_container_width=True,
                ):
                    if not selected_ids:
                        st.warning("少なくとも1件選択してください")
                    else:
                        with st.spinner("配布中..."):
                            bulk_insert_events_to_all_users(selected_ids)
                        st.success(
                            f"✅ {len(selected_ids)}件のイベントを全生徒に配布しました！"
                        )
                        st.balloons()

    st.stop()

# ==========================================================
# ▼ 生徒画面（共通）
# ==========================================================
username_col = "username" if "username" in df.columns else "ユーザー名"
pts_col = "current_points" if "current_points" in df.columns else "現在ポイント"
user_row = df[df[username_col] == selected_user]

if user_row.empty:
    st.warning(f"ユーザー「{selected_user}」が見つかりません。")
    st.stop()

current_points = int(user_row[pts_col].values[0])
last_login = str(user_row[COL_LAST_LOGIN].values[0]) if COL_LAST_LOGIN in df.columns and pd.notna(user_row[COL_LAST_LOGIN].values[0]) else ""
today = today_str()
this_month = this_month_str()

def _get_val(row, col, default=""):
    if col not in row.columns:
        return default
    v = row[col].values[0]
    return v if pd.notna(v) and str(v).strip() else default

streak = int(_get_val(user_row, COL_STREAK, 0))
last_visit = _get_val(user_row, COL_LAST_VISIT, "")
recent_login_dates = _get_val(user_row, COL_RECENT_LOGINS, "")

# ---------- 水平メニューバー ----------
if HAS_OPTION_MENU:
    current_option = PAGE_TO_OPTION.get(st.session_state.page, "ホーム")
    default_index = NAV_OPTIONS.index(current_option) if current_option in NAV_OPTIONS else 0
    selected_nav = option_menu(
        menu_title=None,
        options=NAV_OPTIONS,
        icons=NAV_ICONS,
        default_index=default_index,
        orientation="horizontal",
        styles={
            "container": {"padding": "0.25rem 0", "background-color": "#f5f5f5"},
            "icon": {"color": "#ff9800", "font-size": "1.2rem"},
            "nav-link": {"font-size": "1rem", "text-align": "center", "--hover-color": "#e3f2fd"},
            "nav-link-selected": {"background-color": "#007bff"},
        },
    )
    if selected_nav and OPTION_TO_PAGE.get(selected_nav) != st.session_state.page:
        st.session_state.page = OPTION_TO_PAGE[selected_nav]
        st.rerun()
else:
    cur_opt = PAGE_TO_OPTION.get(st.session_state.page, "ホーム")
    idx = NAV_OPTIONS.index(cur_opt) if cur_opt in NAV_OPTIONS else 0
    sel = st.radio("メニュー", NAV_OPTIONS, index=idx, horizontal=True, label_visibility="collapsed")
    if sel and OPTION_TO_PAGE.get(sel) != st.session_state.page:
        st.session_state.page = OPTION_TO_PAGE[sel]
        st.rerun()

# ---------- CSS ----------
st.markdown("""
<style>
    .header-right { text-align: right; font-size: 1rem; color: #555; margin-bottom: 0.5rem; }
    .mood-btn button { font-size: 1.6rem !important; padding: 1rem !important; min-height: 3.5rem !important; }
    .learning-card { background: #fff; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); padding: 1.5rem; margin: 1rem 0; border: 1px solid #e0e0e0; }
    .test-link-card { display: block; background: linear-gradient(135deg, #1f77b4 0%, #2ca02c 100%); color: white !important; text-align: center; padding: 1.5rem 2rem; border-radius: 12px; font-size: 1.5rem; font-weight: bold; text-decoration: none; box-shadow: 0 4px 12px rgba(0,0,0,0.15); margin: 1rem 0; transition: transform 0.2s, box-shadow 0.2s; }
    .test-link-card:hover { transform: scale(1.02); box-shadow: 0 6px 16px rgba(0,0,0,0.2); color: white !important; }
    .gacha-result-box { text-align: center; padding: 2rem; margin: 2rem 0; border-radius: 16px; font-size: 2rem; font-weight: bold; box-shadow: 0 6px 20px rgba(0,0,0,0.15); }
    .gacha-result-urare { background: linear-gradient(135deg, #ffd700 0%, #ff8c00 100%); color: #333; }
    .gacha-result-super { background: linear-gradient(135deg, #c0c0c0 0%, #a0a0a0 100%); color: #222; }
    .gacha-result-normal { background: linear-gradient(135deg, #87ceeb 0%, #6bb6e0 100%); color: #222; }
    .point-shortage { color: #d32f2f !important; font-size: 1.8rem !important; font-weight: bold !important; }
    .plan-big { font-size: 2rem; font-weight: bold; color: #1f77b4; margin: 1rem 0; padding: 1rem; background: #e3f2fd; border-radius: 12px; }
    .plan-mid { font-size: 1.5rem; font-weight: bold; color: #2e7d32; margin: 0.8rem 0; padding: 0.8rem; background: #e8f5e9; border-radius: 10px; }
    .streak-cell { text-align: center; padding: 0.5rem; border-radius: 12px; font-size: 1rem; }
    .streak-cell.achieved { background: linear-gradient(135deg, #ff9800 0%, #f57c00 100%); color: #fff; font-size: 1.8rem; font-weight: bold; box-shadow: 0 4px 12px rgba(245,124,0,0.4); }
    .streak-cell.today-empty { background: #fff8e1; color: #f9a825; font-size: 1.2rem; }
    .streak-cell.empty { color: #9e9e9e; }

/* ── ダークモード対応：ナビゲーションバー ── */
@media (prefers-color-scheme: dark) {

    /* ナビゲーションのボタンテキストを白に */
    .stButton > button {
        color: #FFFFFF !important;
        border-color: #555555 !important;
    }

    /* 選択中のナビボタンを黄色ベースに */
    .stButton > button[kind="primary"] {
        background-color: #F0C040 !important;
        color: #1a1a1a !important;
    }

    /* カード・ボックス系の背景 */
    div[data-testid="stExpander"] {
        background-color: #2d2d2d !important;
        border-color: #444 !important;
    }

    /* ナビバー（option_menu使用時）のダーク対応 */
    .nav-link {
        color: #EEEEEE !important;
    }
    .nav-link.active {
        background-color: #F0C040 !important;
        color: #1a1a1a !important;
    }

    /* お知らせカードのダーク対応 */
    .stAlert {
        background-color: #3a3a2a !important;
        color: #EEEEEE !important;
    }
}
</style>
""", unsafe_allow_html=True)

col_logo, col_greeting, col_lang, col_logout = st.columns([1, 5, 1, 1])
with col_logo:
    if LOGO_B64:
        st.markdown(
            f'<img src="data:image/png;base64,{LOGO_B64}" '
            f'width="50" style="margin-top:4px;">',
            unsafe_allow_html=True,
        )
with col_greeting:
    st.markdown(
        f"こんにちは、**{selected_user}**さん！　"
        f"現在のポイント：**{current_points}pt**"
    )

lang = st.session_state.lang
t = TEXTS[lang]

with col_lang:
    if st.button(t["lang_btn"], key="lang_toggle_main"):
        st.session_state.lang = LANG_ZH if lang == LANG_JA else LANG_JA
        st.rerun()
with col_logout:
    if st.button(t["logout_btn"], key="logout_btn"):
        st.session_state.logged_in = False
        st.session_state.login_user = ""
        st.session_state.page = PAGE_HOME
        st.rerun()

if st.session_state.page == PAGE_HOME and not st.session_state.toast_shown:
    st.toast(f"こんにちは、{selected_user}さん！")
    st.session_state.toast_shown = True

def render_back_home():
    if st.button("🏠 ホームに戻る", use_container_width=False):
        st.session_state.page = PAGE_HOME
        st.rerun()

if st.session_state.page != PAGE_HOME:
    render_back_home()
    st.markdown("---")

# ==========================================================
# ▼ ホーム画面
# ==========================================================
if st.session_state.page == PAGE_HOME:
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    if last_visit != today:
        new_streak = (streak + 1) if (last_visit == yesterday) else 1
        dates_list = [today] + [d.strip() for d in recent_login_dates.split(",") if d.strip()]
        cutoff_date = (date.today() - timedelta(days=6)).isoformat()
        dates_list = [d for d in dates_list if d >= cutoff_date][:7]
        new_recent = ",".join(dates_list)
        save_user_fields(selected_user, {
            COL_STREAK: new_streak,
            COL_LAST_VISIT: today,
            COL_RECENT_LOGINS: new_recent,
        })
        streak = new_streak
        recent_login_dates = new_recent

    st.markdown("## ホーム")
    st.markdown(
        f'<p style="font-size: 2rem; font-weight: bold; color: #e65100;">'
        f"🔥 連続 {streak}日目！</p>",
        unsafe_allow_html=True,
    )

    st.markdown("**📅 直近7日間**")

    # user_row はこのブロック内の streak 更新後に古いままなので、直近ログイン文字列は recent_login_dates を使う
    try:
        _recent = str(recent_login_dates)
    except Exception:
        _recent = ""

    _days = []
    for _i in range(6, -1, -1):
        _d = date.today() - timedelta(days=_i)
        _logged = _d.isoformat() in _recent
        _is_today = _d == date.today()
        _days.append({
            "date": _d.strftime("%m/%d"),
            "week": ["月", "火", "水", "木", "金", "土", "日"][_d.weekday()],
            "logged": _logged,
            "today": _is_today,
        })

    _cells = ""
    for _item in _days:
        if _item["today"]:
            _bg, _icon, _fc = "#FFF176", "✨", "#333"
        elif _item["logged"]:
            _bg, _icon, _fc = "#FF8C00", "🔥", "#fff"
        else:
            _bg, _icon, _fc = "#e0e0e0", "　", "#888"

        _cells += (
            f'<div style="'
            f"background:{_bg};border-radius:8px;"
            f"text-align:center;padding:6px 0;flex:1;min-width:0;"
            f'">'
            f'<div style="font-size:16px;line-height:1.2;">{_icon}</div>'
            f'<div style="font-size:9px;color:{_fc};">{_item["date"]}</div>'
            f'<div style="font-size:9px;color:{_fc};">{_item["week"]}</div>'
            f"</div>"
        )

    st.markdown(
        f'<div style="display:flex;flex-direction:row;gap:4px;width:100%;">'
        f"{_cells}"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.caption("🔥達成　⬜未達成　✨今日")
    st.markdown("---")

    df_news = load_news()
    df_news_mine = df_news[
        (df_news["target_user"] == "全員") | (df_news["target_user"] == selected_user)
    ]
    if len(df_news_mine) > 0:
        with st.container():
            st.markdown("### 📢 お知らせ")
            for _, row in df_news_mine.iterrows():
                st.warning("⚠️ " + row.get("メッセージ", ""), icon="📢")

    if last_login == today:
        st.markdown("### 今日の気分　登録済み")
        st.caption("今日の気分チェックは完了しています。")
    else:
        st.markdown("### 今日の気分は？")
        st.markdown('<div class="mood-btn">', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            btn_genki = st.button("元気！", use_container_width=True, type="primary")
        with c2:
            btn_futsuu = st.button("ふつう", use_container_width=True)
        with c3:
            btn_nemui = st.button("眠い...", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
        if btn_genki or btn_futsuu or btn_nemui:
            new_pts = current_points + 10
            save_user_fields(selected_user, {
                "current_points": new_pts,
                COL_LAST_LOGIN: today,
            })
            st.success("🎉 ログインボーナスゲット！ +10pt")
            st.rerun()

# ==========================================================
# ▼ 今日の学習
# ==========================================================
elif st.session_state.page == PAGE_SCHEDULE:
    st.markdown("## 📅 今日の学習")

    df_plans = load_plans()
    df_plans["日付"] = df_plans["日付"].astype(str).str[:10]
    today = date.today().isoformat()
    df_today_all = df_plans[
        (df_plans["ユーザー名"] == selected_user)
        & (df_plans["日付"] == today)
        & (df_plans["小計画タスク"] != "（未設定）")
    ].copy()

    if df_today_all.empty:
        st.info("🎉 今日のタスクはありません！")
    else:
        if "task_type" not in df_today_all.columns:
            df_today_all["task_type"] = "lesson"
        else:
            df_today_all["task_type"] = df_today_all["task_type"].fillna(
                "lesson"
            )
        tt = df_today_all["task_type"].astype(str)
        df_lesson = df_today_all[tt != "homework"].copy()
        df_homework = df_today_all[tt == "homework"].copy()

        df_users = load_users()
        _un_col = "username" if "username" in df_users.columns else "ユーザー名"
        _pts_col = (
            "current_points"
            if "current_points" in df_users.columns
            else "現在ポイント"
        )

        def render_task_rows(df_target):
            if df_target.empty:
                st.info("タスクはありません")
                return

            h0, h1, h2, h3, h4, h5 = st.columns([0.5, 4, 1.5, 1, 2, 1.5])
            with h1:
                st.caption("タスク名")
            with h2:
                st.caption("ページ範囲")
            with h3:
                st.caption("動画")
            with h4:
                st.caption("タイマー")
            with h5:
                st.caption("完了")
            st.divider()

            for _, task in df_target.iterrows():
                plan_id = int(task["id"])
                task_name = str(task["小計画タスク"])
                mid_plan = str(task["中計画"])
                is_done = int(task.get("完了フラグ", 0))
                page_rng = str(task.get("page_range", "") or "")
                video_url = str(task.get("video_url", "") or "")

                start_key = f"start_{plan_id}"
                elapsed_key = f"elapsed_{plan_id}"
                if elapsed_key not in st.session_state:
                    st.session_state[elapsed_key] = 0

                col0, col1, col2, col3, col4, col5 = st.columns(
                    [0.5, 4, 1.5, 1, 2, 1.5]
                )

                with col0:
                    st.markdown("✅" if is_done else "⬜")

                with col1:
                    if is_done:
                        st.markdown(
                            f'<span style="color:#b2bec3;text-decoration:line-through;">'
                            f"{task_name}</span>",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(f"**{task_name}**")
                    st.caption(mid_plan)

                with col2:
                    if page_rng and page_rng not in ("nan", "None", ""):
                        st.caption(f"📄 {page_rng}")

                with col3:
                    if video_url and video_url not in ("nan", "", "None"):
                        st.link_button("▶", video_url.strip())

                with col4:
                    if not is_done:
                        t1, t2 = st.columns(2)
                        with t1:
                            if st.button(
                                "▶開始",
                                key=f"start_btn_{plan_id}",
                                use_container_width=True,
                            ):
                                st.session_state[start_key] = datetime.now()
                                st.rerun()
                        with t2:
                            if st.button(
                                "⏹終了",
                                key=f"stop_btn_{plan_id}",
                                use_container_width=True,
                            ):
                                if st.session_state.get(start_key):
                                    elapsed = (
                                        datetime.now()
                                        - st.session_state[start_key]
                                    ).seconds
                                    st.session_state[elapsed_key] += elapsed
                                    st.session_state[start_key] = None
                                st.rerun()
                        elapsed_total = st.session_state.get(elapsed_key, 0)
                        if elapsed_total > 0:
                            mins = elapsed_total // 60
                            secs = elapsed_total % 60
                            st.caption(f"⏱ {mins}分{secs}秒")
                    else:
                        st.caption("✅ 完了済み")

                with col5:
                    if not is_done:
                        if st.button(
                            "完了！",
                            key=f"done_btn_{plan_id}",
                            type="primary",
                            use_container_width=True,
                        ):
                            current_pts = int(
                                df_users[df_users[_un_col] == selected_user][
                                    _pts_col
                                ].iloc[0]
                            )
                            new_pts = current_pts + TASK_TOGGLE_POINTS
                            update_plan_row(plan_id, {"is_done": 1})
                            save_user_fields(
                                selected_user, {"current_points": new_pts}
                            )
                            st.toast(
                                f"🎉 +{TASK_TOGGLE_POINTS}pt 獲得！",
                                icon="🌟",
                            )
                            st.rerun()
                    else:
                        st.markdown(
                            '<span style="color:#00b894;font-size:12px;">🎉 完了！</span>',
                            unsafe_allow_html=True,
                        )
                        if st.button(
                            "↩️ 戻す",
                            key=f"undo_btn_{plan_id}",
                            use_container_width=True,
                        ):
                            current_pts = int(
                                df_users[df_users[_un_col] == selected_user][
                                    _pts_col
                                ].iloc[0]
                            )
                            new_pts = max(0, current_pts - TASK_TOGGLE_POINTS)
                            update_plan_row(plan_id, {"is_done": 0})
                            save_user_fields(
                                selected_user, {"current_points": new_pts}
                            )
                            st.toast(
                                "↩️ タスクを未完了に戻しました",
                                icon="🔄",
                            )
                            st.rerun()

                st.divider()

            total = len(df_target)
            done = int(df_target["完了フラグ"].astype(int).sum())
            st.progress(done / total if total > 0 else 0)
            st.caption(f"進捗：{done}/{total} タスク完了")

        st.markdown("### 📖 学習タスク")
        render_task_rows(df_lesson)

        st.markdown("---")

        homework_done = (
            int(df_homework["完了フラグ"].astype(int).sum())
            if not df_homework.empty
            else 0
        )
        homework_total = len(df_homework)
        badge = (
            f"（{homework_done}/{homework_total} 完了）"
            if homework_total > 0
            else "（なし）"
        )

        st.markdown(f"### 📝 宿題 {badge}")
        render_task_rows(df_homework)

# ==========================================================
# ▼ 計画確認ページ
# ==========================================================
elif st.session_state.page == PAGE_PLAN:
    st.markdown("## 🗺️ 計画確認")

    if "task_added_list" not in st.session_state:
        st.session_state["task_added_list"] = []
    if "task_input_next_date" not in st.session_state:
        st.session_state["task_input_next_date"] = date.today()

    df_plans = load_plans()
    df_plans["日付"] = df_plans["日付"].astype(str).str[:10]

    btn_c1, btn_c2, btn_c3 = st.columns(3)
    with btn_c1:
        if st.button("🎯 大計画を作る", use_container_width=True, key="btn_plan_big"):
            st.session_state.plan_mode = "big"
    with btn_c2:
        if st.button("📚 中計画を作る", use_container_width=True, key="btn_plan_mid"):
            st.session_state.plan_mode = "mid"
    with btn_c3:
        if st.button("✏️ タスクを追加する", use_container_width=True, key="btn_plan_task"):
            st.session_state.plan_mode = "task"

    _pm = st.session_state.get("plan_mode")

    if _pm == "big":
        _cl1, _cl2 = st.columns([6, 1])
        with _cl2:
            if st.button("閉じる", key="plan_close_big"):
                st.session_state.plan_mode = None
                st.rerun()
        st.subheader("🎯 大計画を作る")
        big_plan_input = st.text_input(
            "大計画（目標）を入力してください",
            placeholder="例：2027年2月 私立中学合格！",
            key="form_big_plan_text",
        )
        st.markdown("**📅 いつまでに達成しますか？**")
        col_y, col_m = st.columns(2)
        with col_y:
            deadline_year = st.selectbox(
                "年", [2026, 2027, 2028, 2029], key="big_year"
            )
        with col_m:
            deadline_month = st.selectbox(
                "月", list(range(1, 13)), key="big_month"
            )
        deadline_str = f"{deadline_year}-{str(deadline_month).zfill(2)}"
        if st.button("✅ 大計画を保存", key="form_big_save"):
            if not big_plan_input or not str(big_plan_input).strip():
                st.warning("目標を入力してください")
            else:
                insert_plan_row(
                    selected_user,
                    big_plan_input.strip(),
                    "",
                    "（未設定）",
                    date.today().isoformat(),
                    deadline=deadline_str,
                )
                st.success(
                    f"✅ 大計画「{big_plan_input.strip()}」"
                    f"（期限：{deadline_year}年{deadline_month}月）を保存しました！"
                )
                st.session_state.plan_mode = None
                st.rerun()

    elif _pm == "mid":
        _cm1, _cm2 = st.columns([6, 1])
        with _cm2:
            if st.button("閉じる", key="plan_close_mid_top"):
                st.session_state.plan_mode = None
                st.rerun()
        st.subheader("📚 中計画を作る")

        existing_big_plans = (
            df_plans[df_plans["ユーザー名"] == selected_user]["大計画"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )
        existing_big_plans = [b for b in existing_big_plans if b.strip()]
        if not existing_big_plans:
            st.warning("先に大計画を作成してください。")
            selected_big = None
        else:
            selected_big = st.selectbox(
                "どの大計画に追加しますか？",
                existing_big_plans,
                key="form_mid_big",
            )

        st.markdown("**📅 何月の計画ですか？**")
        _today = date.today()
        _y, _mo = _today.year, _today.month
        month_options: list[str] = []
        for _ in range(12):
            month_options.append(f"{_y}-{_mo:02d}")
            _mo += 1
            if _mo > 12:
                _mo = 1
                _y += 1
        month_labels = [f"{m[:4]}年{int(m[5:7])}月" for m in month_options]
        selected_month_idx = st.selectbox(
            "対象月を選んでください",
            range(len(month_options)),
            format_func=lambda i: month_labels[i],
            key="mid_month",
        )
        selected_month_str = month_options[selected_month_idx]

        mid_type = st.radio(
            "中計画の種類",
            ["📚 教材から選ぶ", "✏️ 自由入力"],
            horizontal=True,
            key="form_mid_type",
        )

        mid_plan_input = ""
        material_id = ""
        mid_page_range = ""
        if mid_type == "📚 教材から選ぶ":
            df_materials = load_materials()
            subj_col = "教科" if "教科" in df_materials.columns else "subject"
            name_col = "教材名" if "教材名" in df_materials.columns else "material_name"
            id_col = "id" if "id" in df_materials.columns else "ID"
            toc_col = (
                "目次データ" if "目次データ" in df_materials.columns else "toc_data"
            )
            if df_materials.empty:
                st.warning("教材が登録されていません")
            else:
                subs = sorted(
                    df_materials[subj_col].dropna().astype(str).unique().tolist()
                )
                subject_filter = st.selectbox(
                    "教科",
                    ["全教科"] + subs,
                    key="form_mid_subject",
                )
                filtered = (
                    df_materials
                    if subject_filter == "全教科"
                    else df_materials[df_materials[subj_col] == subject_filter]
                )
                if len(filtered) == 0:
                    st.warning("教材が登録されていません")
                else:
                    names = filtered[name_col].astype(str).tolist()
                    selected_material = st.selectbox(
                        "教材名を選んでください",
                        names,
                        key="form_mid_material",
                    )
                    mid_plan_input = selected_material
                    mat_row = filtered[filtered[name_col] == selected_material].iloc[0]
                    material_id = str(mat_row.get(id_col, "") or "")

                    toc_list: list = []
                    try:
                        toc_raw = mat_row.get(toc_col, "[]")
                        toc_list = (
                            json.loads(toc_raw)
                            if isinstance(toc_raw, str)
                            else toc_raw
                        )
                    except (json.JSONDecodeError, TypeError, ValueError):
                        toc_list = []
                    if not isinstance(toc_list, list):
                        toc_list = []
                    toc_list = [t for t in toc_list if isinstance(t, dict)]

                    st.markdown("**📄 どこまで進めますか？（ページ範囲）**")
                    range_mode = st.radio(
                        "ページ範囲の指定方法",
                        ["📋 目次から選ぶ", "✏️ 手入力"],
                        horizontal=True,
                        key="mid_range_mode",
                    )

                    if range_mode == "📋 目次から選ぶ" and toc_list:
                        toc_labels = [
                            f"{t.get('単元名', '')}"
                            + (
                                f"（{t.get('ページ範囲', '')}）"
                                if t.get("ページ範囲")
                                else ""
                            )
                            for t in toc_list
                        ]
                        col_s, col_e = st.columns(2)
                        with col_s:
                            start_idx = st.selectbox(
                                "開始（どこから）",
                                range(len(toc_labels)),
                                format_func=lambda i: toc_labels[i],
                                key="mid_toc_start",
                            )
                        with col_e:
                            _end_opts = list(
                                range(int(start_idx), len(toc_labels))
                            )
                            if not _end_opts:
                                _end_opts = [0]
                            end_idx = st.selectbox(
                                "終了（どこまで）",
                                _end_opts,
                                format_func=lambda i: toc_labels[i],
                                key="mid_toc_end",
                            )
                        start_page = str(
                            toc_list[int(start_idx)].get("ページ範囲", "")
                        ).strip()
                        end_page = str(
                            toc_list[int(end_idx)].get("ページ範囲", "")
                        ).strip()
                        mid_page_range = (
                            f"{start_page}〜{end_page}"
                            if start_page and end_page
                            else ""
                        )
                        if mid_page_range:
                            st.info(
                                f"📄 範囲：{toc_labels[int(start_idx)]} 〜 "
                                f"{toc_labels[int(end_idx)]}（{mid_page_range}）"
                            )
                    elif range_mode == "📋 目次から選ぶ" and not toc_list:
                        st.caption(
                            "この教材には目次データがありません。"
                            "手入力で指定してください。"
                        )
                        mid_page_range = st.text_input(
                            "ページ範囲を入力",
                            placeholder="例：P.1〜P.30",
                            key="mid_page_manual",
                        )
                    else:
                        mid_page_range = st.text_input(
                            "ページ範囲を入力",
                            placeholder="例：P.1〜P.30",
                            key="mid_page_manual2",
                        )
        else:
            mid_plan_input = st.text_input(
                "中計画を自由入力してください",
                placeholder="例：英検3級を受験する / 試験に合格する",
                key="form_mid_free",
            )
            material_id = ""
            mid_page_range = ""

        if st.button("✅ 中計画を保存", key="form_mid_save"):
            _mid = (
                mid_plan_input.strip()
                if isinstance(mid_plan_input, str)
                else str(mid_plan_input).strip()
            )
            _pr = (
                str(mid_page_range).strip()
                if mid_page_range is not None
                else ""
            )
            if not selected_big or not _mid:
                st.warning("大計画と中計画を入力してください")
            else:
                insert_plan_row(
                    selected_user,
                    selected_big,
                    _mid,
                    "（未設定）",
                    date.today().isoformat(),
                    material_id=material_id,
                    month_plan=selected_month_str,
                    page_range=_pr,
                )
                _yl = selected_month_str[:4]
                _ml = int(selected_month_str[5:7])
                st.success(
                    f"✅ {_yl}年{_ml}月の中計画「{_mid}」を保存しました！"
                )
                st.session_state.plan_mode = None
                st.rerun()

    elif _pm == "task":
        _ct1, _ct2 = st.columns([6, 1])
        with _ct2:
            if st.button("閉じる", key="plan_close_task_top"):
                st.session_state.plan_mode = None
                st.rerun()
        st.subheader("✏️ タスクを追加する")

        df_user_plans = df_plans[df_plans["ユーザー名"] == selected_user]
        big_plans = (
            df_user_plans["大計画"].dropna().astype(str).unique().tolist()
        )
        big_plans = [b for b in big_plans if b.strip()]
        mid_plans_df = pd.DataFrame()
        task_toc_list: list = []
        if not big_plans:
            st.warning("先に大計画を作成してください。")
            selected_big_for_task = None
            selected_mid_for_task = None
        else:
            selected_big_for_task = st.selectbox(
                "大計画を選んでください",
                big_plans,
                key="task_big",
            )
            mid_plans_df = df_user_plans[
                df_user_plans["大計画"] == selected_big_for_task
            ]
            mid_plans = [
                m
                for m in mid_plans_df["中計画"].dropna().astype(str).unique().tolist()
                if m.strip() and m != "（未設定）"
            ]
            if not mid_plans:
                st.warning(
                    "この大計画に中計画がありません。先に中計画を追加してください。"
                )
                selected_mid_for_task = None
            else:
                selected_mid_for_task = st.selectbox(
                    "中計画を選んでください",
                    mid_plans,
                    key="task_mid",
                )

            if selected_mid_for_task is not None and len(mid_plans_df) > 0:
                try:
                    sub_mid = mid_plans_df[
                        mid_plans_df["中計画"] == selected_mid_for_task
                    ]
                    mat_id_val = None
                    if "material_id" in sub_mid.columns and len(sub_mid) > 0:
                        for v in sub_mid["material_id"].values:
                            if pd.notna(v) and str(v).strip():
                                mat_id_val = v
                                break
                    if mat_id_val:
                        df_mat = load_materials()
                        id_m = "id" if "id" in df_mat.columns else "ID"
                        toc_m = (
                            "目次データ"
                            if "目次データ" in df_mat.columns
                            else "toc_data"
                        )
                        mat_match = df_mat[
                            df_mat[id_m].astype(str) == str(mat_id_val)
                        ]
                        if len(mat_match) > 0:
                            toc_raw = mat_match.iloc[0].get(toc_m, "[]")
                            task_toc_list = (
                                json.loads(toc_raw)
                                if isinstance(toc_raw, str)
                                else toc_raw
                            )
                except (json.JSONDecodeError, TypeError, ValueError, KeyError):
                    task_toc_list = []
                if not isinstance(task_toc_list, list):
                    task_toc_list = []
                task_toc_list = [t for t in task_toc_list if isinstance(t, dict)]

        task_type = st.radio(
            "タスクの種類",
            ["📖 学習タスク", "📝 宿題"],
            horizontal=True,
            key="task_type_radio",
        )
        task_type_val = "homework" if task_type == "📝 宿題" else "lesson"

        st.markdown("**📝 タスク名を設定してください**")
        if len(task_toc_list) == 0:
            task_input_mode = "✏️ 自由入力"
        else:
            task_input_mode = st.radio(
                "入力方法",
                ["📋 目次から選ぶ", "✏️ 自由入力"],
                horizontal=True,
                key="task_input_mode",
            )

        if task_input_mode == "📋 目次から選ぶ" and task_toc_list:
            toc_labels_task = [
                f"{t.get('単元名', '')}"
                + (f"（{t.get('ページ範囲', '')}）" if t.get("ページ範囲") else "")
                for t in task_toc_list
            ]
            selected_toc_idx = st.selectbox(
                "単元を選んでください",
                range(len(toc_labels_task)),
                format_func=lambda i: toc_labels_task[i],
                key="task_toc_select",
            )
            _tn = str(
                task_toc_list[int(selected_toc_idx)].get("単元名", "")
            ).strip()
            _pr = str(
                task_toc_list[int(selected_toc_idx)].get("ページ範囲", "")
            ).strip()
            st.info(f"📖 {_tn}　📄 {_pr}")
            task_name = st.text_input(
                "タスク名（変更可）",
                value=_tn,
                key="task_name_override",
            )
            page_range = st.text_input(
                "ページ範囲（変更可）",
                value=_pr,
                key="task_page_override",
            )
        else:
            task_name = st.text_input(
                "タスク名",
                placeholder="例：計算ドリル P.1-5 を解く",
                key="task_name_free",
            )
            page_range = st.text_input(
                "ページ範囲（任意）",
                placeholder="例：P.1-5",
                key="task_page_free",
            )

        video_url = st.text_input(
            "動画URL（任意）",
            placeholder="https://youtube.com/...",
            key="task_video",
        )

        st.markdown("**📅 何日に行いますか？**")
        start_date = st.date_input(
            "実施日",
            value=st.session_state["task_input_next_date"],
        )
        st.caption("複数日に分ける場合は「何日分のタスクを作成しますか？」で対応します。")
        weekday_options = ["月", "火", "水", "木", "金", "土", "日"]
        jp_wd_to_int = {d: i for i, d in enumerate(weekday_options)}
        selected_weekdays = st.multiselect(
            "学習曜日",
            weekday_options,
            default=["月", "火", "水", "木", "金"],
            key="task_weekdays",
        )
        days = st.number_input(
            "何日分のタスクを作成しますか？",
            min_value=1,
            max_value=30,
            value=1,
            key="task_days",
        )

        if st.button("➕ タスクを追加", type="primary", key="form_task_add"):
            if not task_name or not str(task_name).strip():
                st.warning("タスク名を入力してください")
            elif not selected_big_for_task or not selected_mid_for_task:
                st.warning("大計画と中計画を選んでください")
            elif not selected_weekdays:
                st.warning("学習曜日を1つ以上選んでください")
            else:
                wd_set = {jp_wd_to_int[w] for w in selected_weekdays if w in jp_wd_to_int}
                current_date = start_date
                total = 0
                n_days = int(days)
                last_date = start_date
                vu = (video_url or "").strip()
                pr = (page_range or "").strip()
                for d in range(n_days):
                    while current_date.weekday() not in wd_set:
                        current_date += timedelta(days=1)
                    suffix = f" ({d + 1}/{n_days})" if n_days > 1 else ""
                    insert_plan_row(
                        selected_user,
                        selected_big_for_task,
                        selected_mid_for_task,
                        str(task_name).strip() + suffix,
                        current_date.isoformat(),
                        video_url=vu,
                        page_range=pr,
                        task_type=task_type_val,
                    )
                    last_date = current_date
                    current_date += timedelta(days=1)
                    total += 1

                st.session_state["task_added_list"].append(
                    {
                        "date": last_date.strftime("%m/%d"),
                        "task": str(task_name).strip(),
                        "page": pr,
                        "count": total,
                    }
                )
                st.session_state["task_input_next_date"] = last_date + timedelta(days=1)
                st.rerun()

        if st.session_state["task_added_list"]:
            st.markdown("---")
            st.markdown("**📋 追加済みタスク（今回のセッション）**")
            for item in st.session_state["task_added_list"]:
                page_str = f"　📄 {item['page']}" if item.get("page") else ""
                cnt = item.get("count", 1)
                count_str = f"　×{cnt}日" if cnt > 1 else ""
                st.success(
                    f"✅ {item['date']}　{item['task']}{page_str}{count_str}"
                )
            st.markdown(
                f"**合計 {sum(i['count'] for i in st.session_state['task_added_list'])} 件追加済み**"
            )

        st.markdown("---")
        col_done, col_clear = st.columns([3, 1])
        with col_done:
            if st.button(
                "🏁 入力を完了して閉じる",
                type="primary",
                use_container_width=True,
                key="form_task_done_close",
            ):
                st.session_state.plan_mode = None
                st.session_state["task_added_list"] = []
                st.session_state["task_input_next_date"] = date.today()
                st.rerun()
        with col_clear:
            if st.button(
                "🗑️ ログをクリア",
                use_container_width=True,
                key="form_task_clear_log",
            ):
                st.session_state["task_added_list"] = []
                st.rerun()

    user_plans = df_plans[df_plans["ユーザー名"] == selected_user].copy()

    tab_cal, tab_list = st.tabs(["📅 カレンダー", "📋 一覧"])

    with tab_cal:
        df_user = df_plans[
            (df_plans["ユーザー名"] == selected_user)
            & (df_plans["小計画タスク"] != "（未設定）")
            & (df_plans["日付"] != "")
            & (df_plans["日付"].notna())
        ].copy()

        if not CALENDAR_AVAILABLE:
            st.warning(
                "streamlit-calendarが利用できません。"
                "requirements.txtにstreamlit-calendar==1.3.1を追加してください。"
            )
        elif df_user.empty:
            st.info(
                "まだ計画がありません。"
                "上の「タスクを追加する」から計画を作成してください。"
            )
        else:
            events = []
            color_map = {
                "国語": "#FF6B6B",
                "算数": "#4ECDC4",
                "理科": "#45B7D1",
                "社会": "#96CEB4",
                "英語": "#FFEAA7",
                "中国語": "#DDA0DD",
            }
            default_color = "#74B9FF"

            for _, row in df_user.iterrows():
                try:
                    task_date = str(row["日付"])[:10]
                    task_name = str(row["小計画タスク"])
                    mid_plan = str(row["中計画"])
                    is_done = int(row.get("完了フラグ", 0))

                    event_color = default_color
                    for subject, color in color_map.items():
                        if subject in mid_plan or subject in task_name:
                            event_color = color
                            break

                    if is_done:
                        event_color = "#B2BEC3"

                    events.append(
                        {
                            "title": ("✅ " if is_done else "") + task_name,
                            "start": task_date,
                            "end": task_date,
                            "color": event_color,
                            "extendedProps": {
                                "mid_plan": mid_plan,
                                "is_done": is_done,
                                "page_range": str(row.get("page_range", "")),
                            },
                        }
                    )
                except Exception:
                    continue

            # ── イベント（試験・行事）をカレンダーに追加 ──
            EVENT_COLOR_MAP = {
                "exam": {"color": "#E17055", "icon": "📝"},  # 試験・検定
                "deadline": {"color": "#FDCB6E", "icon": "⏰"},  # 締切・願書
                "event": {"color": "#6C5CE7", "icon": "🎉"},  # 行事・イベント
                "other": {"color": "#A29BFE", "icon": "📌"},  # その他
            }

            df_events = load_events(selected_user)
            for _, ev in df_events.iterrows():
                etype = str(ev.get("event_type", "other"))
                meta = EVENT_COLOR_MAP.get(etype, EVENT_COLOR_MAP["other"])
                events.append({
                    "title": meta["icon"] + " " + str(ev["event_name"]),
                    "start": str(ev["event_date"])[:10],
                    "end": str(ev["event_date"])[:10],
                    "color": meta["color"],
                    "extendedProps": {
                        "type": "event",
                        "etype": etype,
                        "note": str(ev.get("note", "")),
                    },
                })

            calendar_options = {
                "editable": False,
                "selectable": True,
                "headerToolbar": {
                    "left": "prev,next today",
                    "center": "title",
                    "right": "dayGridMonth,timeGridWeek,listWeek",
                },
                "initialView": "dayGridMonth",
                "locale": "ja",
                "height": 650,
                "dayMaxEvents": 3,
                "businessHours": True,
                "weekends": True,
            }

            calendar_css = """
    .fc-event {
        font-size: 11px !important;
        padding: 1px 3px !important;
        border-radius: 4px !important;
        cursor: pointer !important;
    }
    .fc-toolbar-title {
        font-size: 1.2em !important;
        font-weight: bold !important;
    }
    .fc-day-today {
        background-color: #FFF9C4 !important;
    }
    """

            # ────────────────────────────
            # 大計画・中計画サマリーパネル
            # ────────────────────────────
            if "cal_view_year" not in st.session_state:
                st.session_state["cal_view_year"] = date.today().year
            if "cal_view_month" not in st.session_state:
                st.session_state["cal_view_month"] = date.today().month

            view_year = st.session_state["cal_view_year"]
            view_month = st.session_state["cal_view_month"]
            view_month_str = f"{view_year}-{str(view_month).zfill(2)}"

            col_prev, col_title, col_next = st.columns([1, 4, 1])
            with col_prev:
                if st.button("◀ 前月", key="summary_prev"):
                    if view_month == 1:
                        st.session_state["cal_view_year"] -= 1
                        st.session_state["cal_view_month"] = 12
                    else:
                        st.session_state["cal_view_month"] -= 1
                    st.rerun()
            with col_title:
                title_html = (
                    f'<h4 style="text-align:center;margin:0;">'
                    f"📊 {view_year}年{view_month}月の計画サマリー"
                    f"</h4>"
                )
                st.markdown(title_html, unsafe_allow_html=True)
            with col_next:
                if st.button("次月 ▶", key="summary_next"):
                    if view_month == 12:
                        st.session_state["cal_view_year"] += 1
                        st.session_state["cal_view_month"] = 1
                    else:
                        st.session_state["cal_view_month"] += 1
                    st.rerun()

            _ds = df_user["日付"].astype(str).str[:10]
            df_month = (
                df_user[_ds.str.startswith(view_month_str, na=False)].copy()
                if not df_user.empty
                else pd.DataFrame()
            )

            if df_month.empty:
                st.info(f"{view_year}年{view_month}月のタスクはありません。")
            else:
                big_plans_month = df_month["大計画"].unique().tolist()

                for big in big_plans_month:
                    df_big = df_month[df_month["大計画"] == big]

                    total_tasks = len(
                        df_big[df_big["小計画タスク"] != "（未設定）"]
                    )
                    done_tasks = int(df_big["完了フラグ"].astype(int).sum())
                    progress = done_tasks / total_tasks if total_tasks > 0 else 0

                    deadline_val = (
                        df_big["deadline"].iloc[0]
                        if "deadline" in df_big.columns
                        else ""
                    )
                    deadline_label = ""
                    _dv = str(deadline_val).strip() if deadline_val is not None else ""
                    if _dv and len(_dv) == 7 and _dv[4] == "-":
                        deadline_label = (
                            f"　⏰ 期限：{_dv[:4]}年{int(_dv[5:7])}月"
                        )

                    big_header_html = (
                        f'<div style="background:linear-gradient(90deg,#667eea 0%,#764ba2 100%);'
                        f'color:white;padding:8px 16px;border-radius:8px;'
                        f'margin:8px 0 4px 0;font-weight:bold;">'
                        f"🎯 {big}{deadline_label}"
                        f"&nbsp;&nbsp;"
                        f'<span style="font-size:12px;font-weight:normal;">'
                        f"{done_tasks}/{total_tasks}タスク完了"
                        f"</span></div>"
                    )
                    st.markdown(big_header_html, unsafe_allow_html=True)
                    st.progress(progress)

                    mid_plans_month = [
                        m
                        for m in df_big["中計画"].unique().tolist()
                        if m != "（未設定）"
                    ]
                    mid_cols = st.columns(max(len(mid_plans_month), 1))

                    for i, mid in enumerate(mid_plans_month):
                        df_mid = df_big[df_big["中計画"] == mid]

                        mid_total = len(
                            df_mid[df_mid["小計画タスク"] != "（未設定）"]
                        )
                        mid_done = int(df_mid["完了フラグ"].astype(int).sum())
                        mid_prog = mid_done / mid_total if mid_total > 0 else 0

                        month_val = (
                            df_mid["month_plan"].iloc[0]
                            if "month_plan" in df_mid.columns
                            else ""
                        )
                        month_label = ""
                        _mv = str(month_val).strip() if month_val is not None else ""
                        if _mv and len(_mv) == 7 and _mv[4] == "-":
                            month_label = (
                                f"{_mv[:4]}年{int(_mv[5:7])}月"
                            )

                        card_color = "#74B9FF"
                        for subject, c in color_map.items():
                            if subject in mid:
                                card_color = c
                                break

                        with mid_cols[i % len(mid_cols)]:
                            card_html = (
                                f'<div style="border-left:4px solid {card_color};'
                                f'background:#f8f9fa;padding:8px 12px;'
                                f'border-radius:0 8px 8px 0;margin:4px 2px;font-size:13px;">'
                                f"<b>📚 {mid}</b><br>"
                                f'<span style="color:#636e72;font-size:11px;">{month_label}</span><br>'
                                f'<span style="color:#2d3436;">{mid_done}/{mid_total} タスク</span>'
                                f"</div>"
                            )
                            st.markdown(card_html, unsafe_allow_html=True)
                            st.progress(mid_prog)

            st.markdown("---")

            cal_result = st_calendar(
                events=events,
                options=calendar_options,
                custom_css=calendar_css,
                key="plan_calendar",
            )

            if cal_result and cal_result.get("eventClick"):
                clicked = cal_result["eventClick"]["event"]
                props = clicked.get("extendedProps", {})
                if props.get("type") == "event":
                    et = props.get("etype", "")
                    nt = props.get("note", "") or ""
                    st.info(
                        f"📌 **{clicked['title']}**\n\n"
                        f"種別：`{et}`\n\n"
                        + (f"📝 {nt}\n\n" if nt else "")
                    )
                else:
                    done_txt = "✅ 完了済み" if props.get("is_done") else "⬜ 未完了"
                    st.info(
                        f"📖 **{clicked['title']}**\n\n"
                        f"📚 中計画：{props.get('mid_plan', '')}\n\n"
                        f"📄 ページ範囲：{props.get('page_range', '')}\n\n"
                        f"{done_txt}"
                    )

            st.markdown("---")

            # ── イベント管理 ──
            with st.expander("📌 イベント・試験日を管理する", expanded=False):

                # ── 追加フォーム ──
                st.markdown("**➕ 新しいイベントを追加**")
                ev_col1, ev_col2, ev_col3 = st.columns([3, 2, 2])

                with ev_col1:
                    ev_name = st.text_input(
                        "イベント名",
                        placeholder="例：英検3級 / 漢検4級 / 願書提出締切",
                        key="ev_name",
                    )
                with ev_col2:
                    ev_date = st.date_input("日付", value=date.today(), key="ev_date")
                with ev_col3:
                    ev_type = st.selectbox(
                        "種別",
                        ["exam", "deadline", "event", "other"],
                        format_func=lambda x: {
                            "exam": "📝 試験・検定",
                            "deadline": "⏰ 締切・願書",
                            "event": "🎉 行事・イベント",
                            "other": "📌 その他",
                        }[x],
                        key="ev_type",
                    )

                ev_note = st.text_input(
                    "メモ（任意）",
                    placeholder="例：準会場：〇〇中学校 / 9:30集合",
                    key="ev_note",
                )

                if st.button("📌 カレンダーに追加", type="primary", key="ev_add"):
                    if not ev_name:
                        st.warning("イベント名を入力してください")
                    else:
                        insert_event(
                            selected_user,
                            ev_name,
                            ev_date.isoformat(),
                            ev_type,
                            ev_note,
                        )
                        st.success(f"✅ 「{ev_name}」を{ev_date}に追加しました！")
                        st.rerun()

                st.markdown("---")

                # ── 登録済みイベント一覧 ──
                st.markdown("**📋 登録済みイベント一覧**")
                df_ev_list = load_events(selected_user)

                if df_ev_list.empty:
                    st.caption("登録されたイベントはありません")
                else:
                    # 日付順に並べ替え
                    df_ev_list = df_ev_list.sort_values("event_date")

                    for _, ev_row in df_ev_list.iterrows():
                        etype = str(ev_row.get("event_type", "other"))
                        meta = EVENT_COLOR_MAP.get(etype, EVENT_COLOR_MAP["other"])
                        ev_id = ev_row["id"]
                        ev_dt = str(ev_row["event_date"])[:10]
                        ev_note_val = str(ev_row.get("note", ""))

                        list_col1, list_col2, list_col3 = st.columns([4, 2, 1])
                        with list_col1:
                            st.markdown(
                                f'<span style="background:{meta["color"]};'
                                f'color:white;padding:1px 6px;border-radius:4px;'
                                f'font-size:11px;">{meta["icon"]} '
                                f'{"試験" if etype == "exam" else "締切" if etype == "deadline" else "行事" if etype == "event" else "その他"}'
                                f'</span> **{ev_row["event_name"]}**'
                                + (
                                    f'　<span style="color:#636e72;font-size:12px;">{ev_note_val}</span>'
                                    if ev_note_val and ev_note_val != "nan"
                                    else ""
                                ),
                                unsafe_allow_html=True,
                            )
                        with list_col2:
                            st.caption(f"📅 {ev_dt}")
                        with list_col3:
                            if st.button(
                                "🗑️",
                                key=f"del_ev_{ev_id}",
                                help="このイベントを削除",
                            ):
                                delete_event(ev_id)
                                st.rerun()

            st.markdown("---")
            cols_legend = st.columns(len(color_map) + 1)
            legend_items = list(color_map.items()) + [("完了済み", "#B2BEC3")]
            for i, (subject, color) in enumerate(legend_items):
                with cols_legend[i]:
                    st.markdown(
                        f'<span style="background:{color};padding:2px 8px;'
                        f'border-radius:4px;font-size:12px;color:white;">{subject}</span>',
                        unsafe_allow_html=True,
                    )

            st.markdown("**イベント種別：**")
            legend_event_items = [
                ("📝 試験・検定", "#E17055"),
                ("⏰ 締切・願書", "#FDCB6E"),
                ("🎉 行事", "#6C5CE7"),
                ("📌 その他", "#A29BFE"),
            ]
            cols_ev = st.columns(len(legend_event_items))
            for i, (label, color) in enumerate(legend_event_items):
                with cols_ev[i]:
                    st.markdown(
                        f'<span style="background:{color};padding:2px 8px;'
                        f'border-radius:4px;font-size:12px;color:white;">{label}</span>',
                        unsafe_allow_html=True,
                    )

    with tab_list:
        if user_plans.empty:
            st.info("計画データがありません。")
        else:
            big_plan_list = (
                user_plans["大計画"].dropna().astype(str).unique().tolist()
            )
            big_plan_list = [b for b in big_plan_list if str(b).strip()]

            def parse_mid(mid):
                s = str(mid).strip()
                m = re.match(r"^\[(.*?)\]\s*(.*)$", s)
                if m:
                    return m.group(1).strip(), m.group(2).strip()
                return s, ""

            for bi, big_plan in enumerate(big_plan_list):
                group_df = user_plans[user_plans["大計画"] == big_plan]
                deadline_val = (
                    group_df["deadline"].iloc[0]
                    if "deadline" in group_df.columns
                    else ""
                )
                deadline_label = ""
                dv = str(deadline_val).strip() if deadline_val is not None else ""
                if dv and len(dv) == 7 and dv[4] == "-":
                    deadline_label = (
                        f"（期限：{dv[:4]}年{int(dv[5:7])}月）"
                    )

                col_big_title, col_big_del = st.columns([8, 1])
                with col_big_title:
                    st.markdown(
                        f"## 🎯 大計画：{big_plan} {deadline_label}"
                    )
                with col_big_del:
                    _bk = f"del_big_{bi}"
                    if st.button(
                        "🗑️",
                        key=_bk,
                        help=f"「{big_plan}」とその全タスクを削除",
                    ):
                        st.session_state[f"confirm_del_big_{bi}"] = True

                if st.session_state.get(f"confirm_del_big_{bi}", False):
                    st.error(
                        f"⚠️ 「{big_plan}」とそれに紐づく全ての中計画・タスクを削除します。"
                        "よろしいですか？"
                    )
                    col_yes, col_no = st.columns(2)
                    with col_yes:
                        if st.button(
                            "✅ はい、削除する",
                            key=f"yes_del_big_{bi}",
                        ):
                            delete_plans_by_condition(
                                selected_user, big_plan=big_plan
                            )
                            st.session_state[f"confirm_del_big_{bi}"] = False
                            st.success(f"「{big_plan}」を削除しました")
                            st.rerun()
                    with col_no:
                        if st.button(
                            "❌ キャンセル",
                            key=f"no_del_big_{bi}",
                        ):
                            st.session_state[f"confirm_del_big_{bi}"] = False
                            st.rerun()

                mid_plans = group_df["中計画"].unique()
                for mj, mid in enumerate(mid_plans):
                    mid_group_df = group_df[group_df["中計画"] == mid]
                    mid_tasks = mid_group_df
                    month_val = (
                        mid_group_df["month_plan"].iloc[0]
                        if "month_plan" in mid_group_df.columns
                        else ""
                    )
                    month_label = ""
                    mv = str(month_val).strip() if month_val is not None else ""
                    if mv and len(mv) == 7 and mv[4] == "-":
                        month_label = f"【{mv[:4]}年{int(mv[5:7])}月】"

                    subject, goal = parse_mid(mid)
                    total = len(mid_tasks)
                    done_count = int((mid_tasks["完了フラグ"].astype(int) == 1).sum())
                    progress = done_count / total if total > 0 else 0
                    label = f"{subject}" + (f"：{goal}" if goal else "")
                    title_line = f"{month_label} {label}".strip()
                    col_mid_title, col_mid_del = st.columns([8, 1])
                    with col_mid_title:
                        st.markdown(
                            f"### 📚 {title_line}　（{done_count}/{total} 完了）"
                        )
                    with col_mid_del:
                        del_mid_key = f"del_mid_{bi}_{mj}"
                        if st.button(
                            "🗑️",
                            key=del_mid_key,
                            help=f"「{mid}」とその全タスクを削除",
                        ):
                            st.session_state[f"confirm_{del_mid_key}"] = True

                    if st.session_state.get(f"confirm_{del_mid_key}", False):
                        st.error(
                            f"⚠️ 「{mid}」とそれに紐づく全タスクを削除します。"
                            "よろしいですか？"
                        )
                        col_my, col_mn = st.columns(2)
                        with col_my:
                            if st.button(
                                "✅ はい、削除する",
                                key=f"yes_{del_mid_key}",
                            ):
                                delete_plans_by_condition(
                                    selected_user,
                                    big_plan=big_plan,
                                    mid_plan=mid,
                                )
                                st.session_state[f"confirm_{del_mid_key}"] = False
                                st.success(f"「{mid}」を削除しました")
                                st.rerun()
                        with col_mn:
                            if st.button(
                                "❌ キャンセル",
                                key=f"no_{del_mid_key}",
                            ):
                                st.session_state[f"confirm_{del_mid_key}"] = False
                                st.rerun()

                    st.progress(progress)

                    with st.expander(
                        f"タスク一覧（{subject}）",
                        expanded=False,
                    ):
                        chk_changes = {}
                        for _, trow in mid_tasks.iterrows():
                            t_done = int(trow["完了フラグ"]) == 1
                            plan_id = int(trow["id"])
                            col_check, col_name, col_edit, col_task_del = st.columns(
                                [1, 6, 1, 1]
                            )
                            with col_check:
                                new_done = st.checkbox(
                                    "",
                                    value=t_done,
                                    key=f"plan_chk_{plan_id}",
                                    label_visibility="collapsed",
                                )
                            with col_name:
                                st.markdown(
                                    f"**{trow['小計画タスク']}**　（{trow['日付']}）"
                                )
                            with col_edit:
                                if st.button("編集", key=f"plan_edit_{plan_id}"):
                                    edit_task_dialog(plan_id)
                            with col_task_del:
                                if st.button(
                                    "🗑️",
                                    key=f"del_task_{plan_id}",
                                    help="このタスクを削除",
                                ):
                                    delete_plan_row(plan_id)
                                    st.rerun()
                            if new_done != t_done:
                                chk_changes[plan_id] = new_done

                        if chk_changes:
                            if st.button(
                                "💾 チェックを保存",
                                type="primary",
                                key=f"save_chk_{bi}_{mj}",
                            ):
                                pt_delta = 0
                                for pid, is_done_new in chk_changes.items():
                                    update_plan_row(
                                        pid, {"is_done": 1 if is_done_new else 0}
                                    )
                                    pt_delta += (
                                        TASK_TOGGLE_POINTS
                                        if is_done_new
                                        else -TASK_TOGGLE_POINTS
                                    )
                                new_pts = max(0, current_points + pt_delta)
                                save_user_fields(
                                    selected_user, {"current_points": new_pts}
                                )
                                st.toast("💾 保存しました！")
                                st.rerun()

                        if st.button(
                            f"➕ タスク追加（{subject}）",
                            key=f"add_task_{bi}_{mj}",
                        ):
                            add_task_dialog(mid, selected_user)

# ==========================================================
# ▼ 小テスト
# ==========================================================
elif st.session_state.page == PAGE_TEST:
    st.markdown("## ✏️ 小テスト")
    df_c = load_content()
    type_col = "種別" if "種別" in df_c.columns else "content_type"
    subj_col = "教科" if "教科" in df_c.columns else "subject"
    test_content = df_c[df_c[type_col] == "小テスト"] if len(df_c) else pd.DataFrame()
    if test_content.empty:
        st.info("小テストはまだ登録されていません。")
    else:
        subjects = test_content[subj_col].unique()
        for subject in subjects:
            st.subheader(f"📝 {subject}")
            sub_tests = test_content[test_content[subj_col] == subject]
            for _, row in sub_tests.iterrows():
                title_val = row.get("タイトル", row.get("title", ""))
                url_val = str(row.get("URL", row.get("url", ""))).strip()
                st.markdown(f'<a href="{url_val}" target="_blank" class="test-link-card">📝 {title_val}</a>', unsafe_allow_html=True)

# ==========================================================
# ▼ ガチャ
# ==========================================================
elif st.session_state.page == PAGE_GACHA:
    st.markdown("## 🎰 ガチャ")
    st.markdown("""
<div style="text-align: center; padding: 3rem 1rem;
            background: linear-gradient(135deg, #f5f5f5, #eeeeee);
            border-radius: 16px; margin: 2rem 0;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
    <div style="font-size: 4rem;">🎰</div>
    <h2 style="color: #9e9e9e; font-size: 2rem; margin: 1rem 0;">
        準備中...
    </h2>
    <p style="color: #bdbdbd; font-size: 1.2rem;">
        ガチャ機能は現在準備中です。<br>
        もうしばらくお待ちください！
    </p>
</div>
""", unsafe_allow_html=True)
    st.stop()

    st.markdown("## 🎰 ガチャ")
    st.markdown(f"現在のポイント：**{current_points}pt**　（ガチャ1回：{GACHA_COST}pt）")
    GACHA_TABLE = [
        {"rank": "URレア", "label": "🌟 URレア！　特別賞", "css": "gacha-result-urare", "prob": 5},
        {"rank": "スーパーレア", "label": "⭐ スーパーレア！", "css": "gacha-result-super", "prob": 20},
        {"rank": "ノーマル", "label": "✨ ノーマル", "css": "gacha-result-normal", "prob": 75},
    ]
    if current_points < GACHA_COST:
        st.markdown(f'<p class="point-shortage">ポイントが足りません！（{GACHA_COST}pt必要）</p>', unsafe_allow_html=True)
    else:
        if st.button("🎰 ガチャを引く！", type="primary", use_container_width=True):
            new_pts = current_points - GACHA_COST
            save_user_fields(selected_user, {"current_points": new_pts})
            rand = random.randint(1, 100)
            cumulative = 0
            result = GACHA_TABLE[-1]
            for item in GACHA_TABLE:
                cumulative += item["prob"]
                if rand <= cumulative:
                    result = item
                    break
            st.session_state["gacha_result"] = result
            st.session_state["gacha_user"] = selected_user
            st.session_state["gacha_pts"] = new_pts

    if st.session_state.get("gacha_user") == selected_user and st.session_state.get("gacha_result"):
        result = st.session_state["gacha_result"]
        st.markdown(f'<div class="gacha-result-box {result["css"]}">{result["label"]}</div>', unsafe_allow_html=True)
        if result["rank"] == "URレア":
            st.balloons()
        if st.button("🔄 もう一度引く", key="gacha_reset"):
            st.session_state["gacha_result"] = None
            st.session_state["gacha_user"] = None
            st.session_state["gacha_pts"] = None
            st.rerun()
