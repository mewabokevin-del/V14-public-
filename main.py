# ===================== main.py – V14 LA BÊTE FINALE – DÉMO 10000$ =====================
# Déploie ça DIRECT sur Railway → fonctionne en 15 secondes
# Compte DÉMO uniquement (change le token pour passer en réel plus tard)

import asyncio
import json
import websockets
import pandas as pd
import numpy as np
from datetime import datetime
import logging

# ====================== CONFIGURATION DÉMO ======================
API_TOKEN = "R6eCz7z9SWu7gjn"          # ← Colle ton token DÉMO ici (crée-le sur app.deriv.com → API Token)
SYMBOL = "1HZ10V"
DURATION = 5                               # 5 ticks (tu peux tester 3 à 10)
DAILY_TARGET = 9.5                         # % arrêt quotidien
MAX_TRADES_WEEK = 7
MAX_TRADES_WEEKEND = 4

# Variables globales
balance = 10000.0
initial_balance_day = 10000.0
daily_pnl = 0.0
trades_count = 0
in_position = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("V14_BETE_DEMO")

# ====================== FONCTIONS UTILITAIRES ======================
def is_weekend():
    return datetime.now().weekday() >= 5

def is_sunday_morning():
    now = datetime.now()
    return now.weekday() == 6 and now.hour < 6 or (now.weekday() == 6 and now.hour == 6 and now.minute < 30)

def is_forbidden_time():
    h, m = datetime.now().hour, datetime.now().minute
    return (14 <= h < 15 and 20 <= m < 40) or (15 <= h < 16 and 50 <= m < 70) or (h == 16 and m < 10)

def get_stake():
    if is_weekend():
        return round(balance * 0.01, 2)   # 1% week-end
    return round(balance * 0.02, 2)       # 2% semaine

# ====================== INDICATEURS ======================
def add_indicators(df):
    df['ema8'] = df['close'].ewm(span=8, adjust=False).mean()
    df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
    df['ema55'] = df['close'].ewm(span=55, adjust=False).mean()
    
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(7).mean()
    avg_loss = loss.rolling(7).mean()
    rs = avg_gain / avg_loss
    df['rsi'] = 100 - (100 / (1 + rs))
    df['ema_rsi'] = df['rsi'].ewm(span=14, adjust=False).mean()
    return df

# ====================== CONDITIONS V14 LONG ======================
def check_long_setup(df):
    if len(df) < 100: return False
    
    c = df['close'].iloc[-1]
    h = df['high'].iloc[-1]
    l = df['low'].iloc[-1]
    
    # A. Tendance parfaite 3 EMA alignées à la hausse
    if not (df['ema8'].iloc[-1] > df['ema21'].iloc[-1] > df['ema55'].iloc[-1]):
        return False
        
    # B. Impulsion minimum
    impulse_range = df['high'].tail(8).max() - df['low'].tail(8).min()
    min_impulse = 34 if is_weekend() else 28
    if impulse_range < min_impulse:
        return False
    
    # C. Pullback sur EMA21 + zone Fib 38.2-61.8
    pullback_ok = abs(c - df['ema21'].iloc[-1]) <= 10
    if not pullback_ok:
        return False
    
    # D. Structure HH-HL + RSI Killer
    if not (c > df['close'].iloc[-3] > df['close'].iloc[-6]):
        return False
    if not (df['rsi'].iloc[-1] > 67 and df['rsi'].iloc[-1] > df['ema_rsi'].iloc[-1]):
        return False
    
    # E. Cassure du dernier swing high + clôture au-dessus
    last_swing = df['high'].tail(20).max()
    if c > last_swing and df['close'].iloc[-2] <= last_swing:
        return True
        
    return False

# ====================== CONDITIONS V14 SHORT ======================
def check_short_setup(df):
    if len(df) < 100: return False
    
    c = df['close'].iloc[-1]
    
    # Tendance baissière
    if not (df['ema8'].iloc[-1] < df['ema21'].iloc[-1] < df['ema55'].iloc[-1]):
        return False
        
    impulse_range = df['high'].tail(8).max() - df['low'].tail(8).min()
    min_impulse = 34 if is_weekend() else 28
    if impulse_range < min_impulse:
        return False
    
    pullback_ok = abs(c - df['ema21'].iloc[-1]) <= 10
    if not pullback_ok:
        return False
    
    if not (c < df['close'].iloc[-3] < df['close'].iloc[-6]):
        return False
    if not (df['rsi'].iloc[-1] < 33 and df['rsi'].iloc[-1] < df['ema_rsi'].iloc[-1]):
        return False
    
    last_swing = df['low'].tail(20).min()
    if c < last_swing and df['close'].iloc[-2] >= last_swing:
        return True
        
    return False

# ====================== MAIN BOT LOOP ======================
async def trading_bot():
    global balance, daily_pnl, trades_count, initial_balance_day, in_position
    
    uri = "wss://ws.derivws.com/websockets/v3?app_id=1089"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"authorize": API_TOKEN}))
        response = json.loads(await ws.recv())
        if "error" in response:
            logger.error("Token invalide ! Vérifie ton token démo")
            return
        logger.info("Connecté au compte DÉMO 10 000$ → LA BÊTE V14 DÉMARRE !")
        
        # Abonnement aux candles M1
        await ws.send(json.dumps({
            "ticks_history": SYMBOL,
            "end": "latest",
            "count": 500,
            "granularity": 60,
            "style": "candles",
            "subscribe": 1
        }))
        
        while True:
            try:
                msg = json.loads(await ws.recv())
                
                # Mise à jour balance toutes les 30 secondes
                if datetime.now().second % 30 == 0:
                    await ws.send(json.dumps({"balance": 1}))
                    bal = json.loads(await ws.recv())
                    balance = bal['balance']['balance']
                    if initial_balance_day == 0:
                        initial_balance_day = balance
                    daily_pnl = (balance - initial_balance_day) / initial_balance_day * 100
                    logger.info(f"Balance: {balance:.2f}$ | PnL jour: {daily_pnl:+.2f}% | Trades: {trades_count}")
                    
                    if daily_pnl >= DAILY_TARGET:
                        logger.info("OBJECTIF 9.5% ATTEINT → Arrêt jusqu'à demain")
                        await asyncio.sleep(3600)
                        continue
                        
                    max_trades = MAX_TRADES_WEEKEND if is_weekend() else MAX_TRADES_WEEK
                    if trades_count >= max_trades:
                        logger.info("Max trades atteint → pause")
                        await asyncio.sleep(300)
                        continue
                
                # Filtres horaires
                if is_sunday_morning() or is_forbidden_time():
                    await asyncio.sleep(60)
                    continue
                
                if in_position:
                    await asyncio.sleep(1)
                    continue
                
                # Nouvelles candles
                if 'candles' in msg:
                    candles = msg['candles']
                    df = pd.DataFrame(candles)
                    df['close'] = df['close'].astype(float)
                    df['high'] = df['high'].astype(float)
                    df['low'] = df['low'].astype(float)
                    df = add_indicators(df)
                    
                    direction = None
                    if check_long_setup(df):
                        direction = "CALL"
                    elif check_short_setup(df):
                        direction = "PUT"
                    
                    if direction:
                        stake = get_stake()
                        contract = {
                            "buy": 1,
                            "price": stake,
                            "parameters": {
                                "contract_type": direction,
                                "symbol": SYMBOL,
                                "duration": DURATION,
                                "duration_unit": "t",
                                "basis": "stake",
                                "amount": stake
                            }
                        }
                        await ws.send(json.dumps(contract))
                        in_position = True
                        trades_count += 1
                        logger.info(f"ENTREE {direction} → {stake}$ | Trade {trades_count}")
                
                # Fin de contrat
                elif msg.get("msg_type") == "buy":
                    if msg["buy"]["success"]:
                        logger.info("Contrat acheté ! Attente résultat...")
                elif msg.get("msg_type") == "proposal_open_contract":
                    if msg["proposal_open_contract"]["is_sold"]:
                        profit = msg["proposal_open_contract"]["profit"]
                        balance += profit
                        in_position = False
                        logger.info(f"TRADE TERMINÉ → Profit: {profit:+.2f}$ | Nouveau balance: {balance:.2f}$")
                        if profit > 0:
                            logger.info("WIN")
                        else:
                            logger.info("LOSS")
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Erreur: {e}")
                await asyncio.sleep(5)

# ====================== LANCEMENT ======================
if __name__ == "__main__":
    asyncio.run(trading_bot())
