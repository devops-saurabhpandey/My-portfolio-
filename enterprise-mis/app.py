from fastapi import FastAPI

app = FastAPI(title='Enterprise MIS & Analytics API', version='1.0.0')

@app.get('/health')
def health():
    return {'status': 'ok', 'service': 'enterprise-mis-api'}

@app.get('/api/v1/kpis')
def kpis():
    revenue = 125000.0
    orders = 500
    return {'revenue': revenue, 'orders': orders, 'customers': 320, 'average_order_value': revenue / orders}
