import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import random
import re
import json
from datetime import date, datetime, timedelta
import calendar
import os
import time
import gspread
from google.oauth2.service_account import Credentials

# ========== ▼▼▼ ここだけ書き換えてください ▼▼▼ ==========
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1tP0P_VqTExvmNp-CqKMKf_6GPmr35BDCDjOqL_5NPDY/edit?gid=1236206020#gid=1236206020"
# ========== ▲▲▲ ここだけ書き換えてください ▲▲▲ ==========

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

# ページ設定（タブレット向け）
st.set_page_config(
    page_title="未来塾 生徒用アプリ",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

CSV_PATH = "users.csv"
PLANS_PATH = "plans.csv"
CONTENT_PATH = "content.csv"
NEWS_PATH = "news.csv"
MATERIALS_PATH = "materials.csv"
ADMIN_OPTION = "👨‍🏫 管理者"
ADMIN_PASSWORD = "admin"

COL_LAST_LOGIN = "last_login_date"
COL_LAST_VISIT = "last_visit_date"
COL_STREAK = "streak"
COL_RECENT_LOGINS = "recent_login_dates"
GACHA_COST = 50
TASK_POINTS = 5
TASK_TOGGLE_POINTS = 10

# ページ名
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

YOUTUBE_EMBED_URL = "https://www.youtube.com/embed/dQw4w9WgXcQ"
GOOGLE_FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLScVVn3qGYn48oxTzGLOE0iPzFqYjvQnLexample/viewform"

# ==========================================================
# ▼ gspread 接続ヘルパー（st-gsheets-connection の代替）
# ==========================================================
@st.cache_resource
def get_gspread_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes,
    )
    return gspread.authorize(creds)

def read_worksheet(worksheet_name: str, retries: int = 3) -> pd.DataFrame:
    for attempt in range(retries):
        try:
            client = get_gspread_client()
            sheet = client.open_by_url(SPREADSHEET_URL)
            ws = sheet.worksheet(worksheet_name)
            data = ws.get_all_records()
            return pd.DataFrame(data) if data else pd.DataFrame()
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise e

def write_worksheet(worksheet_name: str, df: pd.DataFrame, retries: int = 3):
    for attempt in range(retries):
        try:
            client = get_gspread_client()
            sheet = client.open_by_url(SPREADSHEET_URL)
            ws = sheet.worksheet(worksheet_name)
            ws.clear()
            ws.update([df.columns.values.tolist()] + df.fillna("").values.tolist())
            return
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise e

# ==========================================================
# ▼ データ読み書き関数
# ==========================================================
@st.cache_data
def load_users():
    df = read_worksheet("users")
    if df is None or df.empty:
        df = pd.DataFrame(columns=["ユーザー名", "現在ポイント", COL_LAST_LOGIN, COL_STREAK, COL_LAST_VISIT, COL_RECENT_LOGINS])
    if COL_LAST_LOGIN not in df.columns:
        df[COL_LAST_LOGIN] = ""
    if COL_STREAK not in df.columns:
        df[COL_STREAK] = 0
    if COL_LAST_VISIT not in df.columns:
        df[COL_LAST_VISIT] = ""
    if COL_RECENT_LOGINS not in df.columns:
        df[COL_RECENT_LOGINS] = ""
    return df

def save_users(df):
    write_worksheet("users", df)
    st.cache_data.clear()

def today_str():
    return date.today().isoformat()

def this_month_str():
    return date.today().strftime("%Y-%m")

def load_plans():
    df = read_worksheet("plans")
    if df is None or df.empty:
        df = pd.DataFrame(columns=["ユーザー名", "大計画", "中計画", "小計画タスク", "日付", "完了フラグ", "video_url", "material_id", "page_range"])
    for col, default in [("video_url", ""), ("material_id", ""), ("page_range", "")]:
        if col not in df.columns:
            df[col] = default
    return df

def save_plans(df):
    write_worksheet("plans", df)

def load_content():
    df = read_worksheet("content")
    if df is None or df.empty:
        df = pd.DataFrame(columns=["教科", "種別", "タイトル", "URL"])
    return df

def save_content(df):
    write_worksheet("content", df)

def load_news():
    df = read_worksheet("news")
    if df is None or df.empty:
        df = pd.DataFrame(columns=["メッセージ", "作成日", "target_user"])
    if "target_user" not in df.columns:
        df["target_user"] = "全員"
    return df

def save_news(df):
    write_worksheet("news", df)

def load_materials():
    df = read_worksheet("materials")
    if df is None or df.empty:
        df = pd.DataFrame(columns=["ID", "教科", "教材名", "出版社", "対象学年", "目次データ"])
    return df

def save_materials(df):
    write_worksheet("materials", df)

# ==========================================================
# ▼ ダイアログ
# ==========================================================
@st.dialog("タスクの編集")
def edit_task_dialog(plan_idx):
    df = load_plans()
    df["日付"] = df["日付"].astype(str).str[:10]
    if plan_idx not in df.index:
        st.warning("タスクが見つかりません。")
        return
    row = df.loc[plan_idx]
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
            if new_task_name.strip():
                df.loc[plan_idx, "小計画タスク"] = new_task_name.strip()
            df.loc[plan_idx, "日付"] = new_date.isoformat()
            save_plans(df)
            st.rerun()
    with col_d:
        if st.button("削除", key="dialog_edit_delete"):
            df = df.drop(index=plan_idx)
            save_plans(df)
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
                new_row = pd.DataFrame([{
                    "ユーザー名": selected_user,
                    "大計画": big_plan,
                    "中計画": mid_plan,
                    "小計画タスク": new_task_name.strip(),
                    "日付": new_task_date.isoformat(),
                    "完了フラグ": 0,
                }])
                df = pd.concat([df, new_row], ignore_index=True)
                save_plans(df)
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

# ==========================================================
# ▼ 共通データ読み込み
# ==========================================================
df = load_users()
df_plans = load_plans()

# サイドバー
st.sidebar.title("👤 ユーザー選択")
st.sidebar.markdown("---")
user_names = df["ユーザー名"].tolist()
options = user_names + [ADMIN_OPTION]
selected_user = st.sidebar.selectbox("名前を選んでください", options=options, index=0)

# ==========================================================
# ▼ 管理者画面
# ==========================================================
if selected_user == ADMIN_OPTION:
    if "admin_ok" not in st.session_state:
        st.session_state.admin_ok = False
    pwd = st.sidebar.text_input("パスワード", type="password", key="admin_pwd")
    if st.sidebar.button("ログイン", key="admin_login") and pwd == ADMIN_PASSWORD:
        st.session_state.admin_ok = True
        st.rerun()
    if not st.session_state.admin_ok:
        st.info("👨‍🏫 管理者を選択しました。パスワードを入力してログインしてください。")
        st.stop()

    st.title("👨‍🏫 管理者画面")
    tab_dash, tab_content, tab_materials, tab_news = st.tabs(["📊 生徒の進捗一覧", "📎 教材管理", "📚 教材マスター", "📢 お知らせ管理"])

    with tab_dash:
        st.subheader("生徒の進捗ダッシュボード")
        df_u = load_users()
        dash = df_u[["ユーザー名", "現在ポイント", COL_STREAK, COL_LAST_VISIT]].copy()
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
        if "教科" not in df_c.columns:
            df_c = pd.DataFrame(columns=["教科", "種別", "タイトル", "URL"])
            save_content(df_c)
        for subject in ["国語", "算数", "理科", "社会"]:
            with st.expander(f"📚 {subject}", expanded=True):
                sub = df_c[df_c["教科"] == subject] if len(df_c) else pd.DataFrame()
                for idx, row in sub.iterrows():
                    c1, c2 = st.columns([4, 1])
                    with c1:
                        url_preview = (row.get("URL") or "")[:60] + ("..." if len(row.get("URL") or "") > 60 else "")
                        st.markdown(f"**{row.get('タイトル', '')}**（{row.get('種別', '')}）　{url_preview}")
                    with c2:
                        if st.button("削除", key=f"content_del_{subject}_{idx}"):
                            df_c = load_content()
                            df_c = df_c.drop(index=idx)
                            save_content(df_c)
                            st.rerun()
                        if st.button("編集", key=f"content_edit_{subject}_{idx}"):
                            st.session_state[f"content_editing_{subject}"] = idx
                            st.rerun()
                adding = st.session_state.get(f"content_adding_{subject}")
                editing_idx = st.session_state.get(f"content_editing_{subject}")
                show_form = adding or (editing_idx is not None)
                if show_form:
                    df_c = load_content()
                    if editing_idx is not None and editing_idx in df_c.index:
                        row = df_c.loc[editing_idx]
                        default_tit = row.get("タイトル", "")
                        default_typ = row.get("種別", "動画")
                        if default_typ == "フォーム":
                            default_typ = "小テスト"
                        default_url = row.get("URL", "")
                    else:
                        default_tit = default_url = ""
                        default_typ = "動画"
                    form_suffix = f"edit_{editing_idx}" if editing_idx is not None else "new"
                    tit = st.text_input("タイトル", value=default_tit, key=f"ctitle_{subject}_{form_suffix}")
                    typ = st.selectbox("種別", ["動画", "小テスト"], index=0 if default_typ == "動画" else 1, key=f"ctype_{subject}_{form_suffix}")
                    url_label = "小テストURL" if typ == "小テスト" else "動画URL"
                    url = st.text_input(url_label, value=default_url, key=f"curl_{subject}_{form_suffix}")
                    if st.button("保存", key=f"csave_{subject}") and tit and url:
                        df_c = load_content()
                        if editing_idx is not None and editing_idx in df_c.index:
                            df_c.at[editing_idx, "タイトル"] = tit
                            df_c.at[editing_idx, "種別"] = typ
                            df_c.at[editing_idx, "URL"] = url
                        else:
                            df_c = pd.concat([df_c, pd.DataFrame([{"教科": subject, "種別": typ, "タイトル": tit, "URL": url}])], ignore_index=True)
                        save_content(df_c)
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
                st.session_state.materials_toc_draft.append({"単元名": toc_unit.strip(), "ページ範囲": toc_pages.strip() or "-"})
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
                    df_m = load_materials()
                    try:
                        new_id = int(df_m["ID"].dropna().max()) + 1 if len(df_m) else 1
                    except (ValueError, TypeError):
                        new_id = 1
                    toc_json = json.dumps(st.session_state.materials_toc_draft, ensure_ascii=False)
                    new_row = pd.DataFrame([{"ID": new_id, "教科": mat_kyouka, "教材名": mat_name.strip(), "出版社": mat_pub.strip(), "対象学年": mat_grade.strip(), "目次データ": toc_json}])
                    df_m = pd.concat([df_m, new_row], ignore_index=True)
                    save_materials(df_m)
                    st.session_state.materials_toc_draft = []
                    st.success("教材を保存しました。")
                    st.rerun()
        else:
            st.caption("単元名とページ範囲を入力して「追加」を押すと、ここに目次が溜まります。最後に「教材を保存」で保存します。")
        st.markdown("---")
        st.subheader("登録済み教材一覧")
        df_m = load_materials()
        if len(df_m) == 0:
            st.info("まだ教材が登録されていません。")
        else:
            df_display = df_m[["ID", "教科", "教材名", "出版社", "対象学年"]].copy()
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            st.markdown("**詳細（目次）を表示**")
            mat_options = [f"ID{row['ID']} {row['教材名']}（{row['教科']}）" for _, row in df_m.iterrows()]
            sel_idx = st.selectbox("教材を選択", range(len(mat_options)), format_func=lambda i: mat_options[i], key="mat_sel_detail")
            if sel_idx is not None and 0 <= sel_idx < len(df_m):
                toc_str = df_m.iloc[sel_idx].get("目次データ", "[]")
                try:
                    toc_list = json.loads(toc_str) if isinstance(toc_str, str) else toc_str
                except Exception:
                    toc_list = []
                if toc_list:
                    for item in toc_list:
                        st.markdown(f"- **{item.get('単元名', '')}** … {item.get('ページ範囲', '')}")
                else:
                    st.caption("目次データはありません。")

    with tab_news:
        st.subheader("お知らせメッセージ（ホームに表示）")
        df_n = load_news()
        user_names = load_users()["ユーザー名"].tolist()
        for idx, row in df_n.iterrows():
            c1, c2 = st.columns([4, 1])
            with c1:
                target = row.get("target_user", "全員")
                st.markdown(f"- **[{target}]** {row.get('メッセージ', '')}")
            with c2:
                if st.button("削除", key=f"news_del_{idx}"):
                    df_n = df_n.drop(index=idx)
                    save_news(df_n)
                    st.rerun()
        if st.button("➕ お知らせを追加", key="news_add_btn"):
            st.session_state["news_adding"] = True
        if st.session_state.get("news_adding"):
            msg = st.text_area("メッセージ", key="new_news_msg")
            target_options = ["全員"] + user_names
            target_user = st.selectbox("対象（全員 / 生徒名）", options=target_options, key="news_target_user")
            if st.button("登録", key="news_save_btn") and msg.strip():
                df_n = load_news()
                df_n = pd.concat([df_n, pd.DataFrame([{"メッセージ": msg.strip(), "作成日": today_str(), "target_user": target_user}])], ignore_index=True)
                save_news(df_n)
                st.session_state["news_adding"] = False
                st.rerun()
            if st.button("キャンセル", key="news_cancel_btn"):
                st.session_state["news_adding"] = False
                st.rerun()

    st.stop()

# ==========================================================
# ▼ 生徒画面（共通）
# ==========================================================
user_row = df[df["ユーザー名"] == selected_user]
current_points = int(user_row["現在ポイント"].values[0])
last_login = str(user_row[COL_LAST_LOGIN].values[0]) if pd.notna(user_row[COL_LAST_LOGIN].values[0]) else ""
today = today_str()
this_month = this_month_str()

def _get_val(row, col, default=""):
    v = row[col].values[0]
    return v if pd.notna(v) and str(v).strip() else default

streak = int(user_row[COL_STREAK].values[0]) if COL_STREAK in df.columns and pd.notna(user_row[COL_STREAK].values[0]) else 0
last_visit = _get_val(user_row, COL_LAST_VISIT, "") if COL_LAST_VISIT in df.columns else ""
recent_login_dates = _get_val(user_row, COL_RECENT_LOGINS, "") if COL_RECENT_LOGINS in df.columns else ""

# ---------- 水平メニューバー ----------
if HAS_OPTION_MENU:
    current_option = PAGE_TO_OPTION.get(st.session_state.page, "ホーム")
    default_index = NAV_OPTIONS.index(current_option) if current_option in NAV_OPTIONS else 0
    selected = option_menu(
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
    if selected and OPTION_TO_PAGE.get(selected) != st.session_state.page:
        st.session_state.page = OPTION_TO_PAGE[selected]
        st.rerun()
else:
    cur_opt = PAGE_TO_OPTION.get(st.session_state.page, "ホーム")
    idx = NAV_OPTIONS.index(cur_opt) if cur_opt in NAV_OPTIONS else 0
    sel = st.radio("メニュー", NAV_OPTIONS, index=idx, horizontal=True, label_visibility="collapsed")
    if sel and OPTION_TO_PAGE.get(sel) != st.session_state.page:
        st.session_state.page = OPTION_TO_PAGE[sel]
        st.rerun()

# ---------- CSS / ヘッダー ----------
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
        cutoff = (date.today() - timedelta(days=6)).isoformat()
        dates_list = [d for d in dates_list if d >= cutoff][:7]
        new_recent = ",".join(dates_list)
        df.loc[df["ユーザー名"] == selected_user, COL_STREAK] = new_streak
        df.loc[df["ユーザー名"] == selected_user, COL_LAST_VISIT] = today
        df.loc[df["ユーザー名"] == selected_user, COL_RECENT_LOGINS] = new_recent
        save_users(df)
        streak = new_streak
        recent_login_dates = new_recent

    st.markdown("## ホーム")

    df_news = load_news()
    if "target_user" not in df_news.columns:
        df_news["target_user"] = "全員"
    df_news_mine = df_news[(df_news["target_user"] == "全員") | (df_news["target_user"] == selected_user)]
    if len(df_news_mine) > 0:
        with st.container():
            st.markdown("### 📢 お知らせ")
            for _, row in df_news_mine.iterrows():
                st.warning("⚠️ " + row.get("メッセージ", ""), icon="📢")
            st.markdown("---")

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
    for idx, col in enumerate(cols):
        with col:
            info = day_infos[idx]
            st.markdown(f'<div class="{info["css"]}"><span style="display:block; font-size: inherit;">{info["icon"]}</span><span style="display:block; font-size: 0.85rem; margin-top: 0.2rem;">{info["label"]}</span></div>', unsafe_allow_html=True)
    cols_w = st.columns(7)
    for idx, col in enumerate(cols_w):
        with col:
            st.markdown(f'<p style="text-align: center; font-size: 0.9rem; color: #666; margin-top: -0.3rem;">{day_infos[idx]["weekday"]}</p>', unsafe_allow_html=True)
    st.caption("🔥＝達成済み　⚪＝未達成　✨＝今日（まだならログインして炎を灯そう！）")
    st.markdown("")

    if last_login == today:
        st.markdown("### 今日の気分　登録済み")
        st.caption("今日の気分チェックは完了しています。")
    else:
        st.markdown("### 今日の気分は？")
        st.markdown("")
        st.markdown('<div class="mood-btn">', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            btn_genki = st.button("元気！", use_container_width=True, type="primary")
        with c2:
            btn_futsuu = st.button("ふつう", use_container_width=True)
        with c3:
            btn_nemui = st.button("眠い...", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
        bonus_gotten = False
        if btn_genki or btn_futsuu or btn_nemui:
            current_points += 10
            df.loc[df["ユーザー名"] == selected_user, "現在ポイント"] = current_points
            df.loc[df["ユーザー名"] == selected_user, COL_LAST_LOGIN] = today
            save_users(df)
            bonus_gotten = True
        if bonus_gotten:
            st.success("🎉 ログインボーナスゲット！")

# ==========================================================
# ▼ 今日の学習
# ==========================================================
elif st.session_state.page == PAGE_SCHEDULE:
    st.markdown("## 📅 今日の学習")
    st.markdown("")
    df_plans = load_plans()
    df_plans["日付"] = df_plans["日付"].astype(str).str[:10]
    today_plans = df_plans[(df_plans["ユーザー名"] == selected_user) & (df_plans["日付"] == today)]

    def subject_from_mid(mid):
        s = str(mid).strip()
        m = re.match(r"^\[(.*?)\]", s)
        return m.group(1).strip() if m else s

    df_materials = load_materials()

    if today_plans.empty:
        st.info("今日の学習タスクはありません。")
    else:
        for idx, row in today_plans.iterrows():
            done = int(row["完了フラグ"]) == 1
            status_icon = "✅" if done else "⬜"
            subject = subject_from_mid(row.get("中計画", ""))
            task_name = str(row.get("小計画タスク", ""))
            header_label = f"{status_icon} {subject} : {task_name}"
            with st.expander(header_label, expanded=not done):
                mat_id = row.get("material_id")
                if pd.notna(mat_id) and str(mat_id).strip() and len(df_materials):
                    try:
                        mid_int = int(float(mat_id))
                        mat_row = df_materials[df_materials["ID"].astype(int) == mid_int]
                        if not mat_row.empty:
                            mat_name = mat_row.iloc[0].get("教材名", "")
                            page_range = str(row.get("page_range", "")).strip() or ""
                            if page_range:
                                st.markdown(f"📖 **使用教材:** {mat_name} P.{page_range}")
                            else:
                                st.markdown(f"📖 **使用教材:** {mat_name}")
                    except (ValueError, TypeError):
                        pass
                video_url = row.get("video_url")
                if pd.notna(video_url) and str(video_url).strip():
                    st.video(str(video_url).strip())
                if f"task_start_{idx}" not in st.session_state:
                    st.session_state[f"task_start_{idx}"] = None
                col_sw1, col_sw2, _ = st.columns([1, 1, 2])
                with col_sw1:
                    if st.button("⏱ 開始", key=f"sw_start_{idx}"):
                        st.session_state[f"task_start_{idx}"] = datetime.now().strftime("%H:%M")
                        st.rerun()
                with col_sw2:
                    if st.button("⏹ 終了", key=f"sw_end_{idx}"):
                        st.session_state[f"task_start_{idx}"] = None
                        st.rerun()
                if st.session_state.get(f"task_start_{idx}"):
                    st.caption(f"開始: {st.session_state[f'task_start_{idx}']}")
                if not done:
                    if st.button("✅ 完了！", type="primary", key=f"task_done_{idx}"):
                        df_plans = load_plans()
                        df_plans["日付"] = df_plans["日付"].astype(str).str[:10]
                        df_plans.loc[idx, "完了フラグ"] = 1
                        new_pt = max(0, current_points + TASK_TOGGLE_POINTS)
                        df = load_users()
                        df.loc[df["ユーザー名"] == selected_user, "現在ポイント"] = new_pt
                        save_plans(df_plans)
                        save_users(df)
                        st.balloons()
                        st.rerun()
                else:
                    st.success("このタスクは完了しています。")

# ==========================================================
# ▼ 計画確認ページ
# ==========================================================
elif st.session_state.page == PAGE_PLAN:
    st.markdown("## 🗺️ 計画確認")
    st.markdown("")
    df_plans = load_plans()
    df_plans["日付"] = df_plans["日付"].astype(str).str[:10]
    user_plans = df_plans[df_plans["ユーザー名"] == selected_user].copy()
    month_plans = user_plans[user_plans["日付"].str.startswith(this_month, na=False)].copy()

    calendar_events = []
    for idx, row in user_plans.iterrows():
        done = int(row["完了フラグ"]) == 1
        status_ja = "完了" if done else "未完了"
        calendar_events.append({
            "id": str(idx),
            "title": str(row["小計画タスク"])[:30],
            "start": str(row["日付"])[:10],
            "end": str(row["日付"])[:10],
            "allDay": True,
            "extendedProps": {
                "subject": str(row["中計画"]),
                "status": status_ja,
                "plan_idx": int(idx) if isinstance(idx, (int, float)) else idx,
            },
        })

    if user_plans.empty:
        st.info("計画データがありません。")
    else:
        big_plan = user_plans["大計画"].iloc[0]

        def parse_mid(mid):
            s = str(mid).strip()
            m = re.match(r"^\[(.*?)\]\s*(.*)$", s)
            if m:
                return m.group(1).strip(), m.group(2).strip()
            return s, ""

        st.markdown(f'<div class="plan-big">🎯 大計画：{big_plan}</div>', unsafe_allow_html=True)

        mid_plans = user_plans["中計画"].unique()
        for mid in mid_plans:
            subject, goal = parse_mid(mid)
            mid_tasks = user_plans[user_plans["中計画"] == mid]
            total = len(mid_tasks)
            done_count = int((mid_tasks["完了フラグ"].astype(int) == 1).sum())
            pct = int(done_count / total * 100) if total > 0 else 0
            st.markdown(f'<div class="plan-mid">📚 [{subject}] {goal}　{done_count}/{total}件完了（{pct}%）</div>', unsafe_allow_html=True)
            st.progress(pct / 100)
            with st.expander(f"タスク一覧（{subject}）", expanded=False):
                for tidx, trow in mid_tasks.iterrows():
                    t_done = int(trow["完了フラグ"]) == 1
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        # トグル式チェックボックス
                        new_done = st.checkbox(
                            f"{trow['小計画タスク']}　（{trow['日付']}）",
                            value=t_done,
                            key=f"plan_chk_{tidx}"
                        )
                        # 状態が変わったらポイント更新
                        if new_done != t_done:
                            df_plans = load_plans()
                            df_plans["日付"] = df_plans["日付"].astype(str).str[:10]
                            df_plans.loc[tidx, "完了フラグ"] = 1 if new_done else 0
                            save_plans(df_plans)
                            df_u = load_users()
                            cur_pt = int(df_u.loc[df_u["ユーザー名"] == selected_user, "現在ポイント"].values[0])
                            if new_done:
                                new_pt = cur_pt + TASK_TOGGLE_POINTS
                                st.toast(f"✅ +{TASK_TOGGLE_POINTS}pt 獲得！")
                            else:
                                new_pt = max(0, cur_pt - TASK_TOGGLE_POINTS)
                                st.toast(f"↩️ -{TASK_TOGGLE_POINTS}pt")
                            df_u.loc[df_u["ユーザー名"] == selected_user, "現在ポイント"] = new_pt
                            save_users(df_u)
                            st.rerun()
                    with col2:
                        if st.button("編集", key=f"plan_edit_{tidx}"):
                            edit_task_dialog(tidx)
                if st.button(f"➕ タスク追加（{subject}）", key=f"add_task_{mid}"):
                    add_task_dialog(mid, selected_user)

        # カレンダー表示
        if HAS_STREAMLIT_CALENDAR and calendar_events:
            st.markdown("### 📅 学習カレンダー")
            cal_options = {
                "initialView": "dayGridMonth",
                "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth,listWeek"},
                "locale": "ja",
                "height": 500,
            }
            st_calendar(events=calendar_events, options=cal_options)

# ==========================================================
# ▼ 小テスト
# ==========================================================
elif st.session_state.page == PAGE_TEST:
    st.markdown("## ✏️ 小テスト")
    df_c = load_content()
    test_contents = df_c[df_c["種別"] == "小テスト"] if len(df_c) else pd.DataFrame()
    if test_contents.empty:
        st.info("小テストはまだ登録されていません。")
    else:
        for _, row in test_contents.iterrows():
            subject = row.get("教科", "")
            title = row.get("タイトル", "")
            url = row.get("URL", "")
            if url:
                st.markdown(f'<a href="{url}" target="_blank" class="test-link-card">📝 {subject}：{title}</a>', unsafe_allow_html=True)

# ==========================================================
# ▼ ガチャ
# ==========================================================
elif st.session_state.page == PAGE_GACHA:
    st.markdown("## 🎰 ガチャ")
    st.markdown(f"現在のポイント：**{current_points}pt**　（ガチャ1回：{GACHA_COST}pt）")
    st.markdown("")

    GACHA_TABLE = [
        {"rank": "★★★ ウルトラレア", "label": "🌟 ウルトラレア！特別称号ゲット！", "css": "gacha-result-urare", "weight": 5},
        {"rank": "★★ スーパーレア", "label": "⭐ スーパーレア！すごい！", "css": "gacha-result-super", "weight": 20},
        {"rank": "★ ノーマル", "label": "✨ ノーマル！次こそレアを狙え！", "css": "gacha-result-normal", "weight": 75},
    ]

    if current_points < GACHA_COST:
        st.markdown(f'<p class="point-shortage">ポイントが足りません！あと{GACHA_COST - current_points}pt貯めよう！</p>', unsafe_allow_html=True)
    else:
        if st.button("🎰 ガチャを引く！", type="primary", use_container_width=True):
            weights = [g["weight"] for g in GACHA_TABLE]
            result = random.choices(GACHA_TABLE, weights=weights, k=1)[0]
            new_pt = max(0, current_points - GACHA_COST)
            df = load_users()
            df.loc[df["ユーザー名"] == selected_user, "現在ポイント"] = new_pt
            save_users(df)
            st.markdown(f'<div class="gacha-result-box {result["css"]}">{result["label"]}</div>', unsafe_allow_html=True)
            if result["rank"] == "★★★ ウルトラレア":
                st.balloons()
            st.markdown(f"残りポイント：**{new_pt}pt**")
