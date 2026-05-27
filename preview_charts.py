import streamlit as st
import json
import os
import yfinance as yf
import pandas as pd
import requests
import re

# ==========================================
# 1. 系統核心配置與 Phase 2 頂部無損縮排
# ==========================================
st.set_page_config(page_title="TradeBOT 策略完全體戰情室", page_icon="📈", layout="wide")

# 透過隱藏不必要的元件與優化邊距，達成手機/電腦版頂部完全貼齊、視覺無損縮排
st.markdown("""
    <style>
    /* 移除 Streamlit 原生頂部空白 */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 1rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        max-width: 100% !important;
    }
    /* 自訂深色系主題底色，確保高對比度 */
    .stApp {
        background-color: #121629;
        color: #FFFFFE;
    }
    div[data-testid="stSidebar"] {
        background-color: #161B33;
    }
    h1, h2, h3, h4 {
        color: #EEBBC3 !important;
        margin-top: 0rem !important;
        margin-bottom: 0.3rem !important;
    }
    /* 精緻化展開折疊區塊的框線 */
    .stExpander {
        border: 1px solid rgba(255, 215, 0, 0.3) !important;
        background-color: rgba(255, 255, 255, 0.02) !important;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 輕量化 JSON 大字典讀取模組
# ==========================================
@st.cache_data(ttl=86400)
def load_local_stock_dict():
    json_path = "stock_dict.json"
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}

def get_clean_stock_name(stock_id):
    pure_code = stock_id.split('.')[0]
    local_dict = load_local_stock_dict()
    
    if pure_code in local_dict:
        return local_dict[pure_code]
    
    cache_key = f"name_cache_{pure_code}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]
        
    try:
        ticker = yf.Ticker(stock_id)
        info = ticker.info
        ch_name = info.get('shortName') or info.get('longName') or info.get('name')
        if ch_name:
            for suffix in ["Taiwan", "Stock", "Co.,Ltd.", "Co.", "Ltd."]:
                ch_name = ch_name.replace(suffix, "").strip()
            st.session_state[cache_key] = ch_name
            return ch_name
    except:
        pass
        
    return f"台股 {pure_code}"

# ==========================================
# 3. 記憶體初始化與參數安全移轉
# ==========================================
DEFAULT_GROUP_DATA = {
    "custom_name": "", 
    "logic": "AND (嚴格：需同時符合所有啟用條件)",
    "price_ma": {"val": 20, "active": True},
    "volume_ma": {"val": 5, "active": True},
    "volume_min": {"val": 5, "active": False},
    "volume_burst": {"val": 2.5, "active": False}, 
    "volume_burst_days": {"val": 5, "active": True}, # Phase 2 參數解耦：新增獨立爆量天數
    "rsi": {"val": 75, "active": False},
    "min_volume": {"val": 500, "active": False},
    "watch_list": []
}

if "user_cfg" not in st.session_state:
    st.session_state.user_cfg = {
        "tg_token": "", 
        "tg_chat_id": "",
        "groups": {
            "群組一": json.loads(json.dumps(DEFAULT_GROUP_DATA)),
            "群組二": json.loads(json.dumps(DEFAULT_GROUP_DATA)),
            "群組三": json.loads(json.dumps(DEFAULT_GROUP_DATA))
        }
    }

# 安全檢查：確保舊的緩存資料結構能平滑升級，不遺漏解耦新參數
for g_name, g_body in st.session_state.user_cfg["groups"].items():
    if "volume_burst_days" not in g_body:
        g_body["volume_burst_days"] = {"val": 5, "active": True}

if 'active_group' not in st.session_state: st.session_state.active_group = "群組一"
if 'skip_login' not in st.session_state: st.session_state.skip_login = False
if 'delete_confirm_target' not in st.session_state: st.session_state.delete_confirm_target = ""

user_cfg = st.session_state.user_cfg
active_group = st.session_state.active_group
grp_data = user_cfg["groups"][active_group]

def calculate_rsi(data, periods=14):
    close_delta = data['Close'].diff()
    up = close_delta.clip(lower=0)
    down = -1 * close_delta.clip(upper=0)
    ma_up = up.ewm(com=periods - 1, adjust=True, min_periods=periods).mean()
    ma_down = down.ewm(com=periods - 1, adjust=True, min_periods=periods).mean()
    return 100 - (100 / (1 + (ma_up / ma_down)))

def send_telegram_alert(token, chat_id, message):
    if not token or not chat_id: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try: requests.post(url, json=payload, timeout=5)
    except: pass

# ==========================================
# 4. 漸進式登入頁面與防呆檢查
# ==========================================
has_tg_credentials = bool(user_cfg["tg_token"] and user_cfg["tg_chat_id"])

if not has_tg_credentials and not st.session_state.skip_login:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("📈 策略工作站系統登入")
        st.write("請輸入您的 Telegram 通訊憑證。此資料僅存在您的瀏覽器中，系統不會進行任何雲端備份。")
        
        temp_token = st.text_input("🤖 Telegram Bot Token", type="password")
        temp_chat_id = st.text_input("👤 Telegram Chat ID", type="password")
        
        # 憑證安全中文防呆檢查
        input_error = False
        if temp_token or temp_chat_id:
            if re.search(r'[\u4e00-\u9fff]', temp_token) or re.search(r'[\u4e00-\u9fff]', temp_chat_id):
                st.error("⚠️ 欄位格式錯誤：憑證內含有中文字元，請重新檢查並確認輸入內容。")
                input_error = True
        
        c_btn1, c_btn2 = st.columns(2)
        with c_btn1:
            if st.button("🔓 登入", type="primary", use_container_width=True):
                if temp_token and temp_chat_id and not input_error:
                    user_cfg["tg_token"], user_cfg["tg_chat_id"] = temp_token, temp_chat_id
                    st.rerun()
        with c_btn2:
            if st.button("➡️ 略過 (僅看盤)", use_container_width=True):
                st.session_state.skip_login = True
                st.rerun()
        
        st.write("---")
        with st.expander("❓ 第一次使用？如何獲取 Telegram Token 與 ID？"):
            st.markdown(
"""<div style="background-color: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px;">
<p style="font-size: 16px; color: #EEBBC3; font-weight: bold; margin-bottom: 15px;">💡 只要 3 分鐘，建立您專屬的私密警報機器人：</p>
<div style="margin-bottom: 18px;">
<span style="color: #F8CA00; font-size: 18px; font-weight: bold;">步驟一：取得 Bot Token 🔑</span>
<div style="margin-left: 32px; margin-top: 6px; line-height: 1.6; color: #E0E0E0;">
1. 在 Telegram 搜尋列尋找 <code style="color:#F8CA00; background:rgba(0,0,0,0.3);">@BotFather</code> (帶有官方藍勾勾)。<br>
2. 點擊對話後，輸入 <code>/newbot</code> 建立新機器人。<br>
3. 幫您的機器人取個顯示名稱 (例如：<code>戰情通報</code>)，以及使用者帳號 (必須以 <code>bot</code> 結尾，例如 <code>MyTrade_bot</code>)。<br>
4. 成功後，BotFather 會給您一串專屬金鑰（例如 <code>1234567890:ABCdef...</code>），這就是您的 <strong>Bot Token</strong>，請複製貼上到上方。
</div>
</div>
<div style="margin-bottom: 18px;">
<span style="color: #F8CA00; font-size: 18px; font-weight: bold;">步驟二：取得 Chat ID 👤</span>
<div style="margin-left: 32px; margin-top: 6px; line-height: 1.6; color: #E0E0E0;">
1. 在 Telegram 搜尋 <code style="color:#F8CA00; background:rgba(0,0,0,0.3);">@userinfobot</code>。<br>
2. 點擊 <code>Start</code>，它會立刻回覆您的帳號資訊，其中 <code>Id</code> 後面的數字（例如 <code>1087654321</code>）就是您的 <strong>Chat ID</strong>。
</div>
</div>
<div style="margin-bottom: 5px;">
<span style="color: #F8CA00; font-size: 18px; font-weight: bold;">步驟三：啟動您的機器人 🚀</span>
<div style="margin-left: 32px; margin-top: 6px; line-height: 1.6; color: #E0E0E0;">
1. 在 Telegram 搜尋您剛剛建立的機器人名稱。<br>
2. 點擊進入並按下 <code>Start</code>，您的專屬戰情室就連線完成了！
</div>
</div>
</div>""", unsafe_allow_html=True)
    st.stop()

# ==========================================
# 5. 左側控制台：雙向策略獨立面板區隔
# ==========================================
st.sidebar.title("⚙️ 交易控制面板")

if has_tg_credentials:
    st.sidebar.success("🟢 個人TG警報：已連線")
    if st.sidebar.button("🔒 登出 (清除個人憑證)", use_container_width=True):
        user_cfg["tg_token"], user_cfg["tg_chat_id"] = "", ""
        st.session_state.skip_login = False
        st.rerun()
else:
    st.sidebar.warning("⚠️ TG警報：未串接")
    if st.sidebar.button("🔐 重新串接 Telegram", use_container_width=True):
        st.session_state.skip_login = False
        st.rerun()

st.sidebar.write("---")
display_name = grp_data.get("custom_name") if grp_data.get("custom_name") else active_group

st.sidebar.subheader(f"🎯 參數調整 ({display_name})")
grp_data["logic"] = st.sidebar.selectbox("多重條件觸發規則", ["AND (嚴格：需同時符合)", "OR (寬鬆：符合任一即觸發)"], index=0 if "AND" in grp_data["logic"] else 1)

# 策略控制排版輔助函式
def render_strategy_param(title, key_name, min_v, max_v, suffix="", step=1.0):
    c1, c2 = st.sidebar.columns([3, 1])
    with c1:
        grp_data[key_name]["val"] = st.slider(title, min_v, max_v, float(grp_data[key_name]["val"]), step=step, key=f"sld_{key_name}")
    with c2:
        grp_data[key_name]["active"] = st.toggle("啟用", value=grp_data[key_name]["active"], key=f"tg_{key_name}")
    status_text = "💡 已啟用" if grp_data[key_name]["active"] else "❌ 忽略"
    st.sidebar.caption(f"**{grp_data[key_name]['val']}{suffix}** | {status_text}")

# 🟢 買方進場策略設定區
st.sidebar.markdown("---")
st.sidebar.markdown("### 🟢 買方進場策略設定")
render_strategy_param("價格突破均線 (Price MA)", "price_ma", 5.0, 60.0, "天", step=1.0)

# 【核心更新】爆量表態控制模組與基準天數完全獨立解耦
st.sidebar.markdown("**🔥 當天爆量表態參數**")
c1, c2 = st.sidebar.columns([3, 1])
with c1:
    grp_data["volume_burst_days"]["val"] = st.slider("爆量對比基準天數", 5, 60, int(grp_data["volume_burst_days"]["val"]), step=1, key="sld_burst_days")
    grp_data["volume_burst"]["val"] = st.slider("當天爆量突破門檻", 1.5, 10.0, float(grp_data["volume_burst"]["val"]), step=0.5, key="sld_burst_mult")
with c2:
    st.write("")
    grp_data["volume_burst"]["active"] = st.toggle("啟用", value=grp_data["volume_burst"]["active"], key="tg_volume_burst")
st.sidebar.caption(f"對比基準：**{grp_data['volume_burst_days']['val']}日均量** ｜ 門檻：**{grp_data['volume_burst']['val']}倍**")

render_strategy_param("RSI 熱度上限", "rsi", 40.0, 95.0, "波段", step=1.0)

# 🔴 賣方出場與避險設定區
st.sidebar.markdown("---")
st.sidebar.markdown("### 🔴 賣方出場與避險設定")
render_strategy_param("N日均量線(跌破均量)", "volume_ma", 3.0, 20.0, "天", step=1.0)
render_strategy_param("前N日窒息量(排除今天)", "volume_min", 3.0, 20.0, "天", step=1.0) 
render_strategy_param("5日最低均量門檻", "min_volume", 100.0, 5000.0, "張", step=100.0)

st.sidebar.write("---")
st.sidebar.info("💡 雲端模式：參數已即時鎖定在您的瀏覽器中。")

# ==========================================
# 6. 右側主畫面與核心邏輯運算
# ==========================================
name1 = user_cfg["groups"]["群組一"].get("custom_name") or "群組一"
name2 = user_cfg["groups"]["群組二"].get("custom_name") or "群組二"
name3 = user_cfg["groups"]["群組三"].get("custom_name") or "群組三"

c_tab1, c_tab2, c_tab3 = st.columns(3)
if c_tab1.button(f"📂 【{name1}】", use_container_width=True, type="primary" if active_group == "群組一" else "secondary"):
    st.session_state.active_group = "群組一"
    st.session_state.delete_confirm_target = ""
    st.rerun()
if c_tab2.button(f"📂 【{name2}】", use_container_width=True, type="primary" if active_group == "群組二" else "secondary"):
    st.session_state.active_group = "群組二"
    st.session_state.delete_confirm_target = ""
    st.rerun()
if c_tab3.button(f"📂 【{name3}】", use_container_width=True, type="primary" if active_group == "群組三" else "secondary"):
    st.session_state.active_group = "群組三"
    st.session_state.delete_confirm_target = ""
    st.rerun()

st.write("---")

c_head, c_rename = st.columns([2, 1])
with c_head:
    st.header(f"📊 {display_name} - 即時快照")
with c_rename:
    new_name = st.text_input("✏️ 重新命名當前群組 (Enter存檔)", value=grp_data.get("custom_name", ""), placeholder="例如: 突破主攻艙")
    if new_name != grp_data.get("custom_name", ""):
        grp_data["custom_name"] = new_name
        st.rerun()

if st.button(f"🔄 立即刷新 {display_name} 數據與個人通報測試", type="secondary", use_container_width=True):
    with st.spinner("獲取行情數據與驗證指標中..."):
        summary_data = []
        triggered_stocks_for_tg = []
        
        for stock_id in grp_data["watch_list"]:
            try:
                # 為了確保極端均線（如60日均量）也能平穩計算不發生邊界報錯，固定抓取 1y 數據
                stock = yf.Ticker(stock_id)
                df = stock.history(period="1y")
                if df.empty: continue
                
                ch_name = get_clean_stock_name(stock_id)
                latest = df.iloc[-1]
                prev_close = df.iloc[-2]['Close'] if len(df) > 1 else latest['Close']
                pct_change = ((latest['Close'] - prev_close) / prev_close) * 100
                
                # 計算各項獨立核心指標
                ma_p_val = df['Close'].rolling(window=int(grp_data["price_ma"]["val"])).mean().iloc[-1]
                ma_v_val = df['Volume'].rolling(window=int(grp_data["volume_ma"]["val"])).mean().iloc[-1]
                
                # 解耦運算：使用全新的 volume_burst_days 計算專屬爆量基準線
                burst_base_val = df['Volume'].rolling(window=int(grp_data["volume_burst_days"]["val"])).mean().iloc[-1]
                
                v_min_days = int(grp_data["volume_min"]["val"])
                history_df = df.iloc[:-1]
                vol_ndays_min = history_df['Volume'].tail(v_min_days).min() if len(history_df) >= v_min_days else 0
                
                df['RSI'] = calculate_rsi(df, 14)
                rsi_val = df['RSI'].iloc[-1]
                vol_5d_avg = df['Volume'].rolling(window=5).mean().iloc[-1]
                
                # 條件觸發器狀態判定
                cond_p = (latest['Close'] > ma_p_val) if grp_data["price_ma"]["active"] else None
                cond_v_ma = (latest['Volume'] < ma_v_val) if grp_data["volume_ma"]["active"] else None
                cond_v_min = (latest['Volume'] <= vol_ndays_min) if grp_data["volume_min"]["active"] else None
                
                # 【核心修改】爆量策略完全依據解耦後的專屬基準線計算倍數
                cond_v_burst = (latest['Volume'] > (burst_base_val * grp_data["volume_burst"]["val"])) if grp_data["volume_burst"]["active"] else None
                
                cond_rsi = (rsi_val < grp_data["rsi"]["val"]) if grp_data["rsi"]["active"] else None
                cond_minv = (vol_5d_avg > (grp_data["min_volume"]["val"] * 1000)) if grp_data["min_volume"]["active"] else None
                
                active_conditions = [c for c in [cond_p, cond_v_ma, cond_v_min, cond_v_burst, cond_rsi, cond_minv] if c is not None]
                
                if not active_conditions: is_triggered = False
                elif "AND" in grp_data["logic"]: is_triggered = all(active_conditions)
                else: is_triggered = any(active_conditions)
                
                # 收集最近 5 天的量能與價格資料供 HTML/SVG 迷你圖表渲染
                recent_df = df.tail(5)
                spark_info = []
                for i in range(len(recent_df)):
                    day_data = recent_df.iloc[i]
                    day_open = day_data['Open']
                    day_close = day_data['Close']
                    # 台股配色標準：收盤大於等於開盤為紅K，小於為綠K
                    k_color = "#FF3B30" if day_close >= day_open else "#00E676"
                    spark_info.append({"volume": day_data['Volume'], "color": k_color})
                
                summary_data.append({
                    "股票代碼": stock_id,
                    "名稱(含ETF)": ch_name,
                    "收盤價": f"${latest['Close']:.2f}",
                    "漲跌幅": f"{pct_change:+.2f}%",
                    "價格突破": "✅ 符合" if cond_p == True else ("❌ 未突破" if cond_p == False else "➖"),
                    "均量萎縮": "✅ 符合" if cond_v_ma == True else ("❌ 偏高" if cond_v_ma == False else "➖"),
                    "前N日窒息": "✅ 創低" if cond_v_min == True else ("❌ 未創低" if cond_v_min == False else "➖"),
                    "當天爆量": "💥 爆量!" if cond_v_burst == True else ("❌ 量平" if cond_v_burst == False else "➖"),
                    "綜合警報": "🔥 策略觸發！" if is_triggered else "⚪ 靜止",
                    "sparkline_data": spark_info
                })
                
                if is_triggered:
                    detail_list = []
                    if grp_data["price_ma"]["active"]: detail_list.append(f"  ├ 價格突破均線：{'✅ 符合' if cond_p else '❌ 未突破'}")
                    if grp_data["volume_ma"]["active"]: detail_list.append(f"  ├ N日均量線萎縮：{'✅ 符合' if cond_v_ma else '❌ 偏高'}")
                    if grp_data["volume_min"]["active"]: detail_list.append(f"  ├ 前N日窒息量低：{'✅ 創低' if cond_v_min else '❌ 未創低'}")
                    if grp_data["volume_burst"]["active"]: detail_list.append(f"  ├ 當天爆量門檻：{'💥 爆量達標' if cond_v_burst else '❌ 未達標'}")
                    if grp_data["rsi"]["active"]: detail_list.append(f"  ├ RSI熱度上限：{'✅ 安全' if cond_rsi else '⚠️ 過熱'}")
                    if grp_data["min_volume"]["active"]: detail_list.append(f"  ├ 最低均量門檻：{'✅ 達標' if cond_minv else '❌ 未達標'}")
                    triggered_stocks_for_tg.append((stock_id.split('.')[0], ch_name, latest['Close'], rsi_val, detail_list))
                    
            except Exception as e:
                err_str = str(e)
                if "Too Many Requests" in err_str or "429" in err_str: 
                    st.error(f"⚠️ 標的 {stock_id} 請求過於頻繁觸發限流，請等10秒重試。")
                else: 
                    st.error(f"標的 {stock_id} 數據讀取異常: {e}")
                
        # ==========================================
        # 7. Phase 2 客製化 HTML / SVG 5日紅綠量能表格 (完全左貼齊，防止縮排代碼塊Bug)
        # ==========================================
        if summary_data:
            html_table = """<table style="width:100%; text-align:left; color:#FFFFFE; border-collapse: collapse; font-family: sans-serif; font-size:15px;">
<tr style="border-bottom: 2px solid rgba(255,215,0,0.4); background-color: #161B33; font-weight: bold;">
<th style="padding: 14px 10px;">股票代碼</th>
<th style="padding: 14px 10px;">公司名稱</th>
<th style="padding: 14px 10px;">當前現價</th>
<th style="padding: 14px 10px;">今日漲跌</th>
<th style="padding: 14px 10px; min-width:150px;">近 5 日紅綠量能棒 (Sparklines)</th>
<th style="padding: 14px 10px;">價格/量能狀態項目</th>
<th style="padding: 14px 10px;">量化策略狀態</th>
</tr>"""

            for res in summary_data:
                spark_data = res["sparkline_data"]
                max_vol = max([d["volume"] for d in spark_data]) if spark_data else 1
                
                # SVG 5日紅綠長條量能圖構建
                sparkline_html = '<div style="display: flex; align-items: flex-end; gap: 5px; height: 35px; padding-top:2px;">'
                if spark_data:
                    for day in spark_data:
                        height_pct = max(12, int((day["volume"] / max_vol) * 100))
                        sparkline_html += f'<div style="width: 14px; height: {height_pct}%; background-color: {day["color"]}; border-radius: 1px;" title="量: {day["volume"]:,}"></div>'
                else:
                    sparkline_html += '<span style="color:#666; font-size:12px;">無量能數據</span>'
                sparkline_html += '</div>'
                
                change_color = "#FF3B30" if "+" in res["漲跌幅"] else ("#00E676" if "-" in res["漲跌幅"] else "#FFFFFE")
                status_style = "color: #F8CA00; font-weight: bold;" if "🔥" in res["綜合警報"] else "color: #A0A5C1;"
                
                # 併入原本的詳細條件狀態，方便用戶在同一個表格橫排一目了然
                quick_status = f"價MA:{res['價格突破']}｜均量:{res['均量萎縮']}｜窒息:{res['前N日窒息']}｜爆量:{res['當天爆量']}"
                
                html_table += f"""<tr style="border-bottom: 1px solid rgba(255,255,255,0.08); background-color: rgba(255,255,255,0.01);">
<td style="padding: 12px 10px; font-weight: 600;">{res["股票代碼"]}</td>
<td style="padding: 12px 10px;">{res["名稱(含ETF)"]}</td>
<td style="padding: 12px 10px; font-weight: 600;">{res["收盤價"]}</td>
<td style="padding: 12px 10px; color: {change_color}; font-weight: bold;">{res["漲跌幅"]}</td>
<td style="padding: 12px 10px;">{sparkline_html}</td>
<td style="padding: 12px 10px; font-size:13px; color:#A0A5C1;">{quick_status}</td>
<td style="padding: 12px 10px; {status_style}">{res["綜合警報"]}</td>
</tr>"""
                
            html_table += "</table>"
            st.markdown(html_table, unsafe_allow_html=True)
            
            # Telegram 通知推播模組 (完全還原原版核心通訊)
            if triggered_stocks_for_tg and has_tg_credentials:
                for sid, name, price, rsi, details in triggered_stocks_for_tg:
                    detail_str = "\n".join(details)
                    tg_msg = (
                        f"🔔 *【雲端網頁觸發通報 - {display_name}】*\n"
                        f"━━━━━━━━━━━━━━━━\n"
                        f"📈 標的：`[{sid}] {name}`\n"
                        f"💰 當前收盤：`{price:.2f} 元`\n"
                        f"🔥 核心RSI值：`{rsi:.1f}`\n\n"
                        f"🛠️ 觸發篩選條件明細：\n{detail_str}\n"
                        f"━━━━━━━━━━━━━━━━"
                    )
                    send_telegram_alert(user_cfg["tg_token"], user_cfg["tg_chat_id"], tg_msg)
                st.success("📩 Telegram 個人明細警報已成功發送至您的手機！")
        else:
            st.info("清單目前為空。")

# ==========================================
# 8. 下方標的管理模組 (防呆機制升級)
# ==========================================
st.write("---")
st.subheader(f"📋 {display_name} 標的管理")
c_add1, c_add2 = st.columns([3, 1])
with c_add1:
    new_stock = st.text_input("輸入代碼 (例如: 2330 或 0050)", placeholder="請輸入純數字代碼，系統會自動轉換為完整格式", key="add_stock_input").strip()
with c_add2:
    st.write("") 
    if st.button("➕ 新增標的", use_container_width=True) and new_stock:
        # 新增股票防呆機制：若輸入含有中文，直接攔截不送出，防止底層查詢崩潰
        if re.search(r'[\u4e00-\u9fff]', new_stock):
            st.error("⚠️ 格式錯誤：請輸入純股票代碼（例如：2330），不支援中文名稱。")
        else:
            formatted_stock = f"{new_stock}.TW"
            if formatted_stock not in grp_data["watch_list"]:
                grp_data["watch_list"].append(formatted_stock)
                st.session_state.delete_confirm_target = ""
                st.rerun()

st.write("目前監控中（具備防誤觸雙擊機制）：")
if grp_data["watch_list"]:
    cols_tags = st.columns(min(len(grp_data["watch_list"]), 6))
    for idx, stock_id in enumerate(grp_data["watch_list"]):
        with cols_tags[idx % 6]:
            is_waiting_confirm = (st.session_state.delete_confirm_target == stock_id)
            btn_label = f"⚠️ 確定刪除 {stock_id.split('.')[0]}？" if is_waiting_confirm else f"{stock_id} ❌"
            if st.button(btn_label, key=f"del_{stock_id}", use_container_width=True):
                if is_waiting_confirm:
                    grp_data["watch_list"].remove(stock_id)
                    st.session_state.delete_confirm_target = ""
                    st.rerun()
                else:
                    st.session_state.delete_confirm_target = stock_id
                    st.rerun()
