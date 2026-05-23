import configparser
import time
from datetime import datetime, time as dt_time
import pandas as pd
import yfinance as yf
import requests

# ==========================================
# 1. 讀取設定檔模組
# ==========================================
config = configparser.ConfigParser()
config.read('config.ini', encoding='utf-8')

TG_TOKEN = config['DEFAULT']['TG_TOKEN']
TG_CHAT_ID = config['DEFAULT']['TG_CHAT_ID']
PRICE_MA = int(config['STRATEGY']['PRICE_MA'])
VOLUME_MA = int(config['STRATEGY']['VOLUME_MA'])
WATCH_LIST = [s.strip() for s in config['MONITOR']['WATCH_LIST'].split(',')]
CHECK_INTERVAL = int(config['SYSTEM']['CHECK_INTERVAL_SECONDS'])

# ==========================================
# 2. 功能模組
# ==========================================
def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("推播錯誤:", e)

def check_strategy(df, stock_id):
    if len(df) < PRICE_MA:
        return False
    
    # 動態讀取設定檔的參數來計算均線
    df['MA_P'] = df['Close'].rolling(window=PRICE_MA).mean()
    df['MA_V'] = df['Volume'].rolling(window=VOLUME_MA).mean()
    
    latest = df.iloc[-1]
    is_breakout = latest['Close'] > latest['MA_P']
    is_shrink = latest['Volume'] < latest['MA_V']
    
    print(f"[{stock_id}] 價: {latest['Close']:.1f}(MA{PRICE_MA}:{latest['MA_P']:.1f}) | 量: {int(latest['Volume'])} (VMA{VOLUME_MA}:{int(latest['MA_V'])})")
    
    return is_breakout and is_shrink

def is_market_open():
    """判斷當前時間是否為台股開盤交易時間 (週一至週五 09:00 - 13:30)"""
    now = datetime.now()
    # 檢查是否為週末
    if now.weekday() >= 5:
        return False
    
    current_time = now.time()
    start_time = dt_time(9, 0, 0)
    end_time = dt_time(13, 30, 0)
    
    return start_time <= current_time <= end_time

# ==========================================
# 3. 主自動化循環排程
# ==========================================
def main():
    print(f"[{datetime.now()}] 量化監控引擎已啟動...")
    print(f"目前監控標的: {WATCH_LIST}")
    print(f"策略參數: 價格 > {PRICE_MA}MA 且 成交量 < {VOLUME_MA}MA")
    
    while True:
        now = datetime.now()
        
        # 判斷開盤時間
        if is_market_open():
            print(f"\n--- 執行盤中定時掃描 ({now.strftime('%H:%M:%S')}) ---")
            
            for stock_id in WATCH_LIST:
                try:
                    stock = yf.Ticker(stock_id)
                    # 盤中抓取，關閉還原股價，確保數據與即時看盤軟體同步
                    df = stock.history(period="50d", auto_adjust=False, back_adjust=False)
                    
                    if df.empty:
                        continue
                        
                    if check_strategy(df, stock_id):
                        latest = df.iloc[-1]
                        msg = f"🔔 *【策略觸發】*\n📈 標的：`{stock_id}`\n符合量縮突破！\n價格：`{latest['Close']:.2f}`\n量：`{int(latest['Volume']):,}`"
                        send_telegram_alert(msg)
                        print(f"  => 🎉 {stock_id} 觸發成功，已發送 TG 警報。")
                        
                except Exception as e:
                    print(f"處理 {stock_id} 異常: {e}")
            
            # 依設定的時間間隔進入休眠，時間到了自動醒來檢查下一次
            time.sleep(CHECK_INTERVAL)
            
        else:
            # 盤後或非交易時間的處理邏輯
            current_time = now.time()
            if current_time > dt_time(13, 30, 0) and now.weekday() < 5:
                print(f"[{now.strftime('%H:%M:%S')}] 今日台股已收盤。程式將自動安全退出。")
                break
            else:
                print(f"[{now.strftime('%H:%M:%S')}] 目前非台股交易時間。每 10 分鐘檢查是否開盤...")
                time.sleep(600) # 非開盤時間不需要密集抓資料，每 10 分鐘醒來確認即可

if __name__ == "__main__":
    main()
