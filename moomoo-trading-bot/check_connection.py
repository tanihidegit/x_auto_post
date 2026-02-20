from moomoo import *

def check_connection():
    try:
        # Use default localhost:11111 which is standard for OpenD
        quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)
        
        # Try to get trading days as a simple connectivity test
        ret, data = quote_ctx.get_trading_days(Market.US, start='2023-01-01', end='2023-01-05')
        
        if ret == RET_OK:
            print("Successfully connected to Moomoo OpenD!")
            print(f"Retrieved {len(data)} trading days.")
        else:
            print(f"Connection made but API returned error: {data}")
            
        quote_ctx.close()
        
    except Exception as e:
        print(f"Failed to connect: {str(e)}")
        print("Please ensure Moomoo OpenD is running and listening on port 11111")

if __name__ == "__main__":
    check_connection()
