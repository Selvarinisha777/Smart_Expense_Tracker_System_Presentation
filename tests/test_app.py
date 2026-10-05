import os, sys, tempfile, unittest
from datetime import date
sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))
_tmp=tempfile.TemporaryDirectory()
os.environ['DATABASE_URL']='sqlite:///'+os.path.join(_tmp.name,'test.db')
os.environ['SECRET_KEY']='test-only-key-not-for-production-0123456789'
from app import app,db
from intelligence import parse_text,classify,budget_summary
class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.client=app.test_client()
        with app.app_context(): db.drop_all(); db.create_all()
        self.token=self.register('first@example.com')['token']
        self.headers={'Authorization':'Bearer '+self.token}
    def register(self,email):
        return self.client.post('/api/auth/register',json={'name':'Test User','email':email,'password':'test-pass-123','income':50000}).get_json()
    def add(self,**changes):
        data={'merchant':'Groceries','amount':100,'category':'Groceries','date':date.today().isoformat()};data.update(changes)
        return self.client.post('/api/transactions',headers=self.headers,json=data)
    def test_crud_and_totals(self):
        tx=self.add(amount=2500).get_json();self.assertIn('id',tx)
        month=date.today().strftime('%Y-%m')
        s=self.client.get('/api/summary?month='+month,headers=self.headers).get_json();self.assertEqual(s['spent'],2500)
        r=self.client.put('/api/transactions/'+str(tx['id']),headers=self.headers,json={'merchant':'Coffee','amount':200,'category':'Dining','date':date.today().isoformat()});self.assertEqual(r.status_code,200)
        self.assertEqual(self.client.delete('/api/transactions/'+str(tx['id']),headers=self.headers).status_code,200)
        self.assertEqual(self.client.get('/api/transactions?month='+month,headers=self.headers).get_json(),[])
    def test_account_isolation(self):
        tx=self.add().get_json(); other=self.register('other@example.com');headers={'Authorization':'Bearer '+other['token']}
        self.assertEqual(self.client.delete('/api/transactions/'+str(tx['id']),headers=headers).status_code,404)
        self.assertEqual(self.client.get('/api/transactions',headers=headers).get_json(),[])
    def test_auth_validation_and_logout(self):
        self.assertEqual(self.client.get('/api/profile').status_code,401)
        self.assertEqual(self.client.post('/api/auth/login',json={'email':'first@example.com','password':'wrong'}).status_code,401)
        self.assertEqual(self.add(amount=-5).status_code,400)
        self.assertEqual(self.add(amount='NaN').status_code,400)
        self.assertEqual(self.add(category='invalid').status_code,400)
        self.assertEqual(self.client.post('/api/logout',headers=self.headers).status_code,200)
        self.assertEqual(self.client.get('/api/profile',headers=self.headers).status_code,401)
    def test_sms_does_not_use_balance(self):
        p=parse_text('INR 450.00 debited at Zomato on 01/10/2026. Avl balance INR 25000.00.','sms')
        self.assertEqual(p['amount'],450);self.assertEqual(p['merchant'],'Zomato');self.assertEqual(p['date'],'2026-10-01')
        self.assertEqual(parse_text('Available balance INR 9000','sms')['amount'],None)
    def test_receipt_prefers_total(self):
        self.assertEqual(parse_text('Fresh Market\nMilk 50\nSubtotal 50\nGrand Total INR 55.00','receipt')['amount'],55)
    def test_rebalance_protects_savings(self):
        s=budget_summary(50000,[{'amount':26500,'category':'Housing','date':'2026-10-01'}],date(2026,10,1),date(2026,11,1))
        self.assertEqual(s['adjusted'],{'Needs':26500,'Wants':13500,'Savings':10000})
        s=budget_summary(50000,[{'amount':45000,'category':'Housing','date':'2026-10-01'},{'amount':15000,'category':'Dining','date':'2026-10-01'}],date(2026,10,1),date(2026,11,1))
        self.assertEqual(s['adjusted']['Savings'],10000);self.assertEqual(s['remaining'],-10000)
    def test_ml_and_csv(self):
        self.assertEqual(classify('zomato food delivery')['category'],'Dining')
        self.assertEqual(classify('unknownmerchantxyz')['category'],'Other')
        self.add(merchant='=evil')
        r=self.client.get('/api/export',headers=self.headers)
        self.assertIn("'=evil",r.get_data(as_text=True));self.assertEqual(r.status_code,200)
    def test_income_update(self):
        self.assertEqual(self.client.put('/api/profile',headers=self.headers,json={'income':60000}).status_code,200)
        self.assertEqual(self.client.get('/api/profile',headers=self.headers).get_json()['income'],60000)
if __name__=='__main__': unittest.main()
