import requests
import json
import os
import time
from datetime import datetime
from statistics import mean

# Myfxbook account IDs
ACCOUNTS = {
    "cent_aggressive": {
        "id": 11855250,
        "name": "Cent Aggressive",
        "tier": "Tier 1",
        "capital_range": "$100 - $999",
        "fee": "$15/month + 0% performance",
        "myfxbook_url": "https://www.myfxbook.com/portfolio/edgefx-cent-aggressive/11855250",
        "signal_url": None
    },
    "cent_conservative": {
        "id": 11855302,
        "name": "Cent Conservative",
        "tier": "Tier 2",
        "capital_range": "$1,000 - $3,000",
        "fee": "$15/month + 20% performance",
        "myfxbook_url": "https://www.myfxbook.com/portfolio/edgefx-cent-conservative/11855302",
        "signal_url": "https://trade.edgefxcopy.com/view/63H6KuV9MVfyOoxI"
    }
}

class MyfxbookAPI:
    BASE_URL = "https://www.myfxbook.com/api"
    
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.session_token = None
        # Use requests.Session for cookie handling
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Origin': 'https://www.myfxbook.com',
            'Referer': 'https://www.myfxbook.com/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        })
    
    def login(self):
        """Login to Myfxbook and get session token"""
        url = f"{self.BASE_URL}/login.json"
        
        # Try with params (GET style)
        params = {
            "email": self.email,
            "password": self.password
        }
        
        try:
            print("🔑 Attempting login to Myfxbook API...")
            
            # First try: GET request (original method)
            response = self.session.get(url, params=params, timeout=30)
            
            # If 403, try POST method instead
            if response.status_code == 403:
                print("⚠️ GET method blocked, trying POST...")
                time.sleep(2)
                response = self.session.post(url, data=params, timeout=30)
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("error"):
                raise Exception(f"Login failed: {data.get('message', 'Unknown error')}")
            
            self.session_token = data.get("session")
            print(f"✅ Logged in successfully. Session: {self.session_token[:20]}...")
            return self.session_token
        
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                print("❌ 403 Forbidden - Myfxbook is blocking API access from GitHub Actions")
                print("💡 This might be an IP block or API restriction")
                print("🔍 Response content:", e.response.text[:200])
            raise Exception(f"Login failed with HTTP {e.response.status_code}: {str(e)}")
        except Exception as e:
            print(f"❌ Login error: {e}")
            raise
    
    def get_account_data(self, account_id):
        """Get account statistics"""
        if not self.session_token:
            raise Exception("Not logged in. Call login() first.")
        
        url = f"{self.BASE_URL}/get-my-accounts.json"
        params = {"session": self.session_token}
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if data.get("error"):
                raise Exception(f"API error: {data.get('message')}")
            
            accounts = data.get("accounts", [])
            for account in accounts:
                if account.get("id") == account_id:
                    return account
            
            raise Exception(f"Account {account_id} not found")
        
        except Exception as e:
            print(f"❌ Error fetching account {account_id}: {e}")
            raise
    
    def get_daily_data(self, account_id):
        """Get daily gain data for calculating monthly averages"""
        if not self.session_token:
            raise Exception("Not logged in")
        
        url = f"{self.BASE_URL}/get-data-daily.json"
        params = {
            "session": self.session_token,
            "id": account_id
        }
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if data.get("error"):
                print(f"⚠️ Daily data error for account {account_id}: {data.get('message')}")
                return None
            
            return data.get("dataDaily", {})
        
        except Exception as e:
            print(f"⚠️ Error fetching daily data for {account_id}: {e}")
            return None

def calculate_monthly_stats(daily_data):
    """Calculate monthly statistics from daily data"""
    if not daily_data:
        return []
    
    monthly_returns = {}
    
    for date_str, gain in daily_data.items():
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
            month_key = date.strftime("%Y-%m")
            
            if month_key not in monthly_returns:
                monthly_returns[month_key] = []
            
            monthly_returns[month_key].append(float(gain))
        except:
            continue
    
    monthly_stats = []
    for month, gains in sorted(monthly_returns.items(), reverse=True):
        month_total = sum(gains)
        month_date = datetime.strptime(month, "%Y-%m")
        
        monthly_stats.append({
            "month": month_date.strftime("%B %Y"),
            "return": round(month_total, 2)
        })
    
    return monthly_stats

def process_account(api, account_key, account_info):
    """Process single account and return formatted data"""
    print(f"\n📊 Processing {account_info['name']}...")
    
    try:
        account_data = api.get_account_data(account_info['id'])
        daily_data = api.get_daily_data(account_info['id'])
        monthly_stats = calculate_monthly_stats(daily_data)
        
        if monthly_stats:
            monthly_returns = [m['return'] for m in monthly_stats]
            min_monthly = min(monthly_returns)
            max_monthly = max(monthly_returns)
            avg_monthly = mean(monthly_returns)
        else:
            min_monthly = 0
            max_monthly = 0
            avg_monthly = 0
        
        result = {
            "name": account_info['name'],
            "tier": account_info['tier'],
            "capital_range": account_info['capital_range'],
            "fee": account_info['fee'],
            "myfxbook_url": account_info['myfxbook_url'],
            "signal_url": account_info['signal_url'],
            "stats": {
                "total_gain": round(float(account_data.get("gain", 0)), 2),
                "min_monthly": round(min_monthly, 2),
                "avg_monthly": round(avg_monthly, 2),
                "max_monthly": round(max_monthly, 2),
                "avg_daily": round(float(account_data.get("dailyGain", 0)), 2),
                "balance": round(float(account_data.get("balance", 0)), 2),
                "equity": round(float(account_data.get("equity", 0)), 2),
                "drawdown": round(float(account_data.get("drawdown", 0)), 2),
                "win_rate": round(float(account_data.get("profitFactor", 0)) * 100, 1) if account_data.get("profitFactor") else 0
            },
            "monthly_history": monthly_stats[:12]
        }
        
        print(f"✅ {account_info['name']}: {result['stats']['total_gain']}% total gain")
        return result
    
    except Exception as e:
        print(f"❌ Failed to process {account_info['name']}: {e}")
        return None

def main():
    email = os.environ.get('MYFXBOOK_EMAIL')
    password = os.environ.get('MYFXBOOK_PASSWORD')
    
    if not email or not password:
        raise Exception("MYFXBOOK_EMAIL and MYFXBOOK_PASSWORD environment variables required")
    
    print("🚀 Starting Myfxbook data update...")
    print(f"📧 Email: {email}")
    
    api = MyfxbookAPI(email, password)
    
    try:
        api.login()
    except Exception as e:
        print("\n" + "="*60)
        print("🚨 MYFXBOOK API ACCESS BLOCKED")
        print("="*60)
        print("Myfxbook is blocking API requests from GitHub Actions.")
        print("This is likely due to IP-based restrictions.")
        print("\nWorkaround: You'll need to run this script locally and")
        print("commit the updated performance_data.json manually.")
        print("="*60)
        raise
    
    performance_data = {
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "accounts": []
    }
    
    for key, info in ACCOUNTS.items():
        account_data = process_account(api, key, info)
        if account_data:
            performance_data["accounts"].append(account_data)
    
    output_file = "performance_data.json"
    with open(output_file, 'w') as f:
        json.dump(performance_data, f, indent=2)
    
    print(f"\n✅ Performance data saved to {output_file}")
    print(f"📊 Updated {len(performance_data['accounts'])} accounts")
    print(f"🕒 Last updated: {performance_data['last_updated']}")

if __name__ == "__main__":
    main()
