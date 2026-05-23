import os
import sys
import time
import json
import threading
import requests
import yfinance as yf
import pandas as pd
import urllib.request
import streamlit.web.cli as stcli

def resolve_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# ==========================================
# 核心演算法：RSI 計算與 TG 溝通模組
# ==========================================
def calculate_rsi(data, periods=14):
    close_delta = data['Close'].diff()
    up = close_delta.clip(lower=0)
    down = -1 * close_delta.clip(upper=0)
    ma_up = up.ewm(com=periods - 1, adjust=True, min_periods=periods).mean()
    ma_down = down.ewm(com=periods - 1, adjust=True, min_periods=periods).mean()
    return 100 - (100 / (1 + (ma_up / ma_down)))

def send_telegram_alert(token, chat_id, message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try: requests.post(url, json=payload, timeout=5)
    except: pass

def check_if_user_acknowledged(token):
    """
    智慧地獄風控：檢查 Telegram 後台更新
    如果使用者在群組中輸入了 'ok'、'OK'、'已讀'、'收到'，則視為已確認，停止轟炸。
    """
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        response = requests.get(url, timeout=5).json()
        if response.get("ok") and response.get("result"):
            # 唯有檢查最近 10 條訊息即可
            for update in reversed(response["result"][-10:]):
                msg = update.get("message", {})
                text = msg.get("text", "").strip().lower()
                if text in ["ok", "已讀", "收到", "k"]:
                    return True
    except: pass
    return False

# ==========================================
# 💥 雙核心：真・全自動背景巡邏與連環轟炸引擎
# ==========================================
def background_monitor_worker():
    config_path = resolve_path("config.json")
    
    # 延遲 15 秒啟動，讓前端網頁與證交所字典快照先完成
    time.sleep(15) 
    print("\n[背景核心] 🤖 真・地獄級自動巡邏機器人已全面上線！24/7 監控中...")
    
    # 用來追蹤哪些標的已經觸發，且正在處於「未讀轟炸狀態」
    # 格式: { "群組名_股票代碼": { "last_alert_time": timestamps, "resolved": False } }
    active_bombing_targets = {}

    while True:
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                
                token = cfg.get("tg_token")
                chat_id = cfg.get("tg_chat_id")
                
                # 有憑證才啟動量化運算
                if token and chat_id:
                    # 先檢查使用者是不是在 TG 回覆「已讀」了？
                    user_read = check_if_user_acknowledged(token)
                    if user_read:
                        # 如果已讀，將所有當前轟炸目標強制解除鎖定 (Reset)
                        if active_bombing_targets:
                            print("[背景核心] 👤 偵測到用戶已讀回覆！解除全域連環轟炸鎖定。")
                            active_bombing_targets.clear()

                    # 輪詢每一個策略群組
                    for g_key, grp_data in cfg.get("groups", {}).items():
                        watch_list = grp_data.get("watch_list", [])
                        display_name = grp_data.get("custom_name") or g_key
                        logic = grp_data.get("logic", "AND")
                        
                        if not watch_list: continue
                        
                        for stock_id in watch_list:
                            bomb_key = f"{g_key}_{stock_id}"
                            
                            # 1. 如果此股票已經觸發且「尚未被已讀」，啟動每 5 分鐘地獄連環轟炸
                            if bomb_key in active_bombing_targets:
                                print(f"[背景核心] 🚨 {stock_id} 處於未確認狀態，觸發連環轟炸...")
                                # 這裡直接進行重發通報，不用重複算 K 線（節省網路流量）
                                tg_msg = f"💥 *【地獄催促 - 未確認警報！】*\n━━━━━━━━━━━━━━━━━━\n⚠️ 策略：`{display_name}`\n📈 標的：`{stock_id}`\n\n📌 *此標的已符合策略，請至下單軟體確認！*\n💡 提示：在 TG 群組輸入 `OK` 或 `已讀` 即可終止此轟炸。"
                                send_telegram_alert(token, chat_id, tg_msg)
                                continue # 跳過後續的重複計算
                            
                            # 2. 正常巡邏計算
                            stock = yf.Ticker(stock_id)
                            df = stock.history(period="65d")
                            if df.empty: continue
                            
                            latest = df.iloc[-1]
                            ma_p = df['Close'].rolling(window=grp_data["price_ma"]["val"]).mean().iloc[-1]
                            ma_v = df['Volume'].rolling(window=grp_data["volume_ma"]["val"]).mean().iloc[-1]
                            vol_ndays_min = df['Volume'].tail(grp_data["volume_min"]["val"]).min()
                            
                            df['RSI'] = calculate_rsi(df, 14)
                            rsi_val = df['RSI'].iloc[-1]
                            vol_5d_avg = df['Volume'].rolling(window=5).mean().iloc[-1]
                            
                            # 條件判定
                            cond_p = (latest['Close'] > ma_p) if grp_data["price_ma"]["active"] else None
                            cond_v_ma = (latest['Volume'] < ma_v) if grp_data["volume_ma"]["active"] else None
                            cond_v_min = (latest['Volume'] <= vol_ndays_min) if grp_data["volume_min"]["active"] else None
                            cond_rsi = (rsi_val < grp_data["rsi"]["val"]) if grp_data["rsi"]["active"] else None
                            cond_minv = (vol_5d_avg > (grp_data["min_volume"]["val"] * 1000)) if grp_data["min_volume"]["active"] else None
                            
                            active_conds = [c for c in [cond_p, cond_v_ma, cond_v_min, cond_rsi, cond_minv] if c is not None]
                            
                            if not active_conds: is_triggered = False
                            elif "AND" in logic: is_triggered = all(active_conds)
                            else: is_triggered = any(active_conds)
                            
                            # 3. 首次符合策略，將其加入「地獄連環轟炸名單」
                            if is_triggered:
                                print(f"[背景核心] 🔥 成功捕獲策略觸發個股: {stock_id}，正式立案轟炸！")
                                active_bombing_targets[bomb_key] = {"trigger_time": time.time()}
                                
                                detail_list = []
                                if grp_data["price_ma"]["active"]: detail_list.append(f"  ├ 價格突破均線：✅ 符合")
                                if grp_data["volume_ma"]["active"]: detail_list.append(f"  ├ N日均量線萎縮：✅ 符合")
                                if grp_data["volume_min"]["active"]: detail_list.append(f"  ├ 創N日窒息量低：✅ 創低")
                                if grp_data["rsi"]["active"]: detail_list.append(f"  ├ RSI熱度上限：✅ 安全")
                                if grp_data["min_volume"]["active"]: detail_list.append(f"  ├ 最低均量門檻：✅ 達標")
                                detail_str = "\n".join(detail_list)
                                
                                tg_msg = (
                                    f"🔔 *【全自動背景巡邏觸發通報】*\n"
                                    f"━━━━━━━━━━━━━━━━━━\n"
                                    f"🎯 策略：`{display_name}`\n"
                                    f"📈 標的：`{stock_id}`\n"
                                    f"💰 當前收盤：`{latest['Close']:.2f} 元`\n"
                                    f"🔥 核心RSI值：`{rsi_val:.1f}`\n\n"
                                    f"🛠️ 觸發篩選條件明細：\n{detail_str}\n"
                                    f"━━━━━━━━━━━━━━━━━━\n"
                                    f"📢 提示：系統已鎖定此標的。請在群組回覆 `OK` 關閉連環通報。"
                                )
                                send_telegram_alert(token, chat_id, tg_msg)
                                
        except Exception as e:
            print(f"[背景核心異常] {e}")
            
        # 🕰️ 核心巡航頻率：每 5 分鐘 (300秒) 全域大掃描一次
        time.sleep(300)

# ==========================================
# 主核心：Streamlit 伺服器啟動區塊
# ==========================================
if __name__ == "__main__":
    # 1. 喚醒隱形防禦核心
    monitor_thread = threading.Thread(target=background_monitor_worker, daemon=True)
    monitor_thread.start()
    
    # 2. 喚醒前端網頁主機
    script_path = resolve_path("ui_dashboard.py")
    sys.argv = [
        "streamlit",
        "run",
        script_path,
        "--global.developmentMode=false",
        "--server.headless=false",  
        "--server.port=8501"
    ]
    sys.exit(stcli.main())
