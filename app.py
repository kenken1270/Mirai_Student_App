# Supabase の plans テーブルに deadline / month_plan 等のカラムを追加してください（未作成だと INSERT が失敗することがあります）。
# 例: ALTER TABLE plans ADD COLUMN IF NOT EXISTS deadline text;
#     ALTER TABLE plans ADD COLUMN IF NOT EXISTS month_plan text;

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
    HAS_STREAMLIT_CALENDAR = True
except ImportError:
    HAS_STREAMLIT_CALENDAR = False

try:
    from streamlit_option_menu import option_menu
    HAS_OPTION_MENU = True
except ImportError:
    HAS_OPTION_MENU = False

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
                                   "deadline", "month_plan"])
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
    }).execute()
    st.cache_data.clear()

def delete_plan_row(plan_id: int):
    sb = get_supabase()
    sb.table("plans").delete().eq("id", plan_id).execute()
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

    st.markdown(f"""
    <div style="text-align:center; padding: 2rem 0;">
        <div style="font-size: 4rem;">🌟</div>
        <h1 style="font-size: 3rem; color: #f9a825; font-weight: bold;">
            {t["school_name"]}
        </h1>
        <p style="font-size: 1.3rem; color: #555; margin-top: 0.5rem;">
            {t["catchcopy"]}
        </p>
    </div>
    """, unsafe_allow_html=True)

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
    st.title("👨‍🏫 管理者画面")
    tab_dash, tab_content, tab_materials, tab_news = st.tabs(
        ["📊 生徒の進捗一覧", "📎 教材管理", "📚 教材マスター", "📢 お知らせ管理"]
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
</style>
""", unsafe_allow_html=True)

_, header_col = st.columns([3, 1])
with header_col:
    st.markdown(f'<p class="header-right">こんにちは、{selected_user}さん！　現在のポイント：<strong>{current_points}pt</strong></p>', unsafe_allow_html=True)

lang = st.session_state.lang
t = TEXTS[lang]

btn_col1, btn_col2 = st.columns([1, 1])
with btn_col1:
    if st.button(t["lang_btn"], key="lang_toggle_main"):
        st.session_state.lang = LANG_ZH if lang == LANG_JA else LANG_JA
        st.rerun()
with btn_col2:
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

    st.markdown(f'<p style="font-size: 2rem; font-weight: bold; color: #e65100;">🔥 連続 {streak}日目！</p>', unsafe_allow_html=True)
    recent_set = set(d.strip() for d in recent_login_dates.split(",") if d.strip())
    today_iso = date.today().isoformat()
    weekdays_ja = ["月", "火", "水", "木", "金", "土", "日"]
    day_infos = []
    for i in range(6, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        is_today = d == today_iso
        achieved = d in recent_set
        if achieved:
            icon = "🔥"; label = "今日" if is_today else d[5:].replace("-", "/"); css_class = "streak-cell achieved"
        elif is_today:
            icon = "✨"; label = "今日"; css_class = "streak-cell today-empty"
        else:
            icon = "⚪"; label = d[5:].replace("-", "/"); css_class = "streak-cell empty"
        wd = date.fromisoformat(d).weekday()
        day_infos.append({"date": d, "icon": icon, "label": label, "css": css_class, "weekday": weekdays_ja[wd]})

    st.markdown("**直近7日間**")
    cols = st.columns(7)
    for idx2, col in enumerate(cols):
        with col:
            info = day_infos[idx2]
            st.markdown(f'<div class="{info["css"]}"><span style="display:block;">{info["icon"]}</span><span style="display:block; font-size: 0.85rem;">{info["label"]}</span></div>', unsafe_allow_html=True)
    cols_w = st.columns(7)
    for idx2, col in enumerate(cols_w):
        with col:
            st.markdown(f'<p style="text-align:center; font-size:0.9rem; color:#666;">{day_infos[idx2]["weekday"]}</p>', unsafe_allow_html=True)
    st.caption("🔥＝達成済み　⚪＝未達成　✨＝今日")
    st.markdown("")

    df_news = load_news()
    df_news_mine = df_news[
        (df_news["target_user"] == "全員") | (df_news["target_user"] == selected_user)
    ]
    if len(df_news_mine) > 0:
        with st.container():
            st.markdown("### 📢 お知らせ")
            for _, row in df_news_mine.iterrows():
                st.warning("⚠️ " + row.get("メッセージ", ""), icon="📢")
            st.markdown("---")

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
    df_plans_today = load_plans()
    df_plans_today["日付"] = df_plans_today["日付"].astype(str).str[:10]
    today_tasks = df_plans_today[
        (df_plans_today["ユーザー名"] == selected_user) & (df_plans_today["日付"] == today)
    ]

    def subject_from_mid(mid):
        s = str(mid).strip()
        m = re.match(r"^\[(.*?)\]", s)
        return m.group(1).strip() if m else s

    df_materials = load_materials()

    if today_tasks.empty:
        st.info("今日の学習タスクはありません。")
    else:
        for _, row in today_tasks.iterrows():
            done = int(row["完了フラグ"]) == 1
            status_icon = "✅" if done else "⬜"
            subject = subject_from_mid(row.get("中計画", ""))
            task_name = str(row.get("小計画タスク", ""))
            plan_id = int(row["id"])
            header_label = f"{status_icon} {subject} : {task_name}"
            with st.expander(header_label, expanded=not done):
                mat_id = row.get("material_id")
                if pd.notna(mat_id) and str(mat_id).strip() and len(df_materials):
                    try:
                        mid_int = int(float(mat_id))
                        id_col_m = "ID" if "ID" in df_materials.columns else "id"
                        mat_row = df_materials[df_materials[id_col_m].astype(int) == mid_int]
                        if not mat_row.empty:
                            mat_name = mat_row.iloc[0].get("教材名", "")
                            page_range = str(row.get("page_range", "")).strip()
                            if page_range:
                                st.markdown(f"📖 **使用教材:** {mat_name} P.{page_range}")
                            else:
                                st.markdown(f"📖 **使用教材:** {mat_name}")
                    except (ValueError, TypeError):
                        pass
                video_url = row.get("video_url")
                if pd.notna(video_url) and str(video_url).strip():
                    st.video(str(video_url).strip())
                sw_key = f"task_start_{plan_id}"
                if sw_key not in st.session_state:
                    st.session_state[sw_key] = None
                col_sw1, col_sw2, _ = st.columns([1, 1, 2])
                with col_sw1:
                    if st.button("⏱ 開始", key=f"sw_start_{plan_id}"):
                        st.session_state[sw_key] = datetime.now().strftime("%H:%M")
                        st.rerun()
                with col_sw2:
                    if st.button("⏹ 終了", key=f"sw_end_{plan_id}"):
                        st.session_state[sw_key] = None
                        st.rerun()
                if st.session_state.get(sw_key):
                    st.caption(f"開始: {st.session_state[sw_key]}")
                if not done:
                    if st.button("✅ 完了！", type="primary", key=f"task_done_{plan_id}"):
                        update_plan_row(plan_id, {"is_done": 1})
                        new_pts = current_points + TASK_TOGGLE_POINTS
                        save_user_fields(selected_user, {"current_points": new_pts})
                        st.balloons()
                        st.rerun()
                else:
                    st.success("このタスクは完了しています。")

# ==========================================================
# ▼ 計画確認ページ
# ==========================================================
elif st.session_state.page == PAGE_PLAN:
    st.markdown("## 🗺️ 計画確認")

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
        if mid_type == "📚 教材から選ぶ":
            df_materials = load_materials()
            subj_col = "教科" if "教科" in df_materials.columns else "subject"
            name_col = "教材名" if "教材名" in df_materials.columns else "material_name"
            id_col = "id" if "id" in df_materials.columns else "ID"
            if df_materials.empty:
                st.warning("教材データがありません。")
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
                if filtered.empty:
                    st.warning("該当する教材がありません。")
                else:
                    names = filtered[name_col].astype(str).tolist()
                    selected_material = st.selectbox(
                        "教材名を選んでください",
                        names,
                        key="form_mid_material",
                    )
                    mid_plan_input = selected_material
                    _rows = filtered[filtered[name_col]
                                    == selected_material]
                    if len(_rows) > 0:
                        material_id = str(
                            _rows.iloc[0].get(id_col, "") or ""
                        )
        else:
            mid_plan_input = st.text_input(
                "中計画を自由入力してください",
                placeholder="例：英検3級を受験する",
                key="form_mid_free",
            )

        if st.button("✅ 中計画を保存", key="form_mid_save"):
            _mid = (
                mid_plan_input.strip()
                if isinstance(mid_plan_input, str)
                else str(mid_plan_input).strip()
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
            mid_plans = df_user_plans[
                df_user_plans["大計画"] == selected_big_for_task
            ]["中計画"].dropna().astype(str).unique().tolist()
            mid_plans = [m for m in mid_plans if m.strip()]
            if not mid_plans:
                st.warning("この大計画に中計画がありません。先に中計画を追加してください。")
                selected_mid_for_task = None
            else:
                selected_mid_for_task = st.selectbox(
                    "中計画を選んでください",
                    mid_plans,
                    key="task_mid",
                )

        task_name = st.text_input(
            "タスク名",
            placeholder="例：計算ドリル P.1-5 を解く",
            key="task_name_input",
        )
        page_range = st.text_input(
            "ページ範囲（任意）",
            placeholder="例：P.1-5",
            key="task_page_range",
        )
        video_url = st.text_input(
            "動画URL（任意）",
            placeholder="https://youtube.com/...",
            key="task_video_url",
        )

        st.markdown("**📅 何日に行いますか？**")
        start_date = st.date_input(
            "実施日",
            value=date.today(),
            key="task_start",
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

        if st.button("✅ タスクを保存", key="form_task_save"):
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
                    )
                    current_date += timedelta(days=1)
                    total += 1
                st.success(f"✅ {total}個のタスクを登録しました！")
                st.session_state.plan_mode = None
                st.rerun()

    user_plans = df_plans[df_plans["ユーザー名"] == selected_user].copy()

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
            st.markdown(
                f'<div class="plan-big">🎯 大計画：{big_plan} {deadline_label}</div>',
                unsafe_allow_html=True,
            )

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
                st.markdown(
                    f'<div class="plan-mid">📚 {title_line}　（{done_count}/{total} 完了）</div>',
                    unsafe_allow_html=True,
                )
                st.progress(progress)

                with st.expander(
                    f"タスク一覧（{subject}）",
                    expanded=False,
                ):
                    chk_changes = {}
                    for _, trow in mid_tasks.iterrows():
                        t_done = int(trow["完了フラグ"]) == 1
                        plan_id = int(trow["id"])
                        col1, col2 = st.columns([4, 1])
                        with col1:
                            new_done = st.checkbox(
                                f"{trow['小計画タスク']}　（{trow['日付']}）",
                                value=t_done,
                                key=f"plan_chk_{plan_id}",
                            )
                            if new_done != t_done:
                                chk_changes[plan_id] = new_done
                        with col2:
                            if st.button("編集", key=f"plan_edit_{plan_id}"):
                                edit_task_dialog(plan_id)

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
