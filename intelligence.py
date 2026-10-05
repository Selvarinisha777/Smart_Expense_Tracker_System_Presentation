"""Small demonstrator model. Scores are similarity, not validated probability."""
import re
from datetime import date,datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
CATEGORIES={'Groceries':'Needs','Housing':'Needs','Utilities':'Needs','Transport':'Needs','Health':'Needs','Dining':'Wants','Shopping':'Wants','Entertainment':'Wants','Savings':'Savings','Other':'Wants'}
TRAINING={
'Groceries':['grocery supermarket vegetables fruits milk bread eggs rice','bigbasket dmart reliance fresh food market','groceries provision store'],
'Housing':['rent landlord apartment housing mortgage','monthly house rent accommodation'],
'Utilities':['electricity power water gas utility bill broadband internet phone recharge','bescom tneb airtel jio vodafone'],
'Transport':['uber ola taxi bus train metro fuel petrol diesel parking','irctc railway transport auto cab'],
'Health':['hospital doctor clinic pharmacy medicine health dental','apollo medical laboratory consultation'],
'Dining':['restaurant cafe coffee lunch dinner takeaway pizza','swiggy zomato food delivery breakfast'],
'Shopping':['amazon flipkart myntra shoes clothing shopping electronics','purchase fashion clothes laptop'],
'Entertainment':['netflix spotify movie cinema games streaming subscription','disney hotstar youtube entertainment'],
'Savings':['savings investment mutual fund deposit emergency fund','sip equity pension savings transfer']}
texts=[]; labels=[]
for label,examples in TRAINING.items():
    for example in examples: texts.append(example); labels.append(label)
vectorizer=TfidfVectorizer(ngram_range=(1,2)); vectors=vectorizer.fit_transform(texts)
model=MultinomialNB(alpha=.2).fit(vectors,labels)
def classify(text):
    vector=vectorizer.transform([text])
    if vector.nnz==0: return dict(category='Other',method='No matching vocabulary; please review')
    return dict(category=str(model.predict(vector)[0]),method='TF-IDF + Naive Bayes; please review')
def parse_text(text,source):
    # Prefer explicit final totals, never a card number or available bank balance.
    patterns=[r'(?:grand\s*total|amount\s*paid|total\s*paid|total\s*amount|(?<!sub)\btotal)\s*[:=]?\s*(?:INR|Rs\.?|₹|\$)?\s*([\d,]+(?:\.\d{1,2})?)',r'(?:debited|spent|paid|purchase(?:\s+of)?)\s*(?:by|for|of)?\s*(?:INR|Rs\.?|₹|\$)?\s*([\d,]+(?:\.\d{1,2})?)',r'(?:INR|Rs\.?|₹|\$)\s*([\d,]+(?:\.\d{1,2})?)\s*(?:debited|spent|paid)']
    amount=None
    for p in patterns:
        found=re.findall(p,text,re.I)
        if found:
            amount=float(found[-1].replace(',','')); break
    merchant_match=re.search(r'(?:\bat\b|\bto\b)\s+([A-Za-z][A-Za-z0-9 &.\-]{1,65}?)(?=\s+(?:on|using|via|ref|avl|balance)\b|[;\n]|$)',text,re.I)
    lines=[x.strip() for x in text.splitlines() if x.strip()]
    merchant=merchant_match.group(1).strip() if merchant_match else (lines[0][:120] if source=='receipt' and lines else '')
    dt=date.today().isoformat()
    for p,formats in [(r'\b\d{4}-\d{2}-\d{2}\b',['%Y-%m-%d']),(r'\b\d{2}[/-]\d{2}[/-]\d{4}\b',['%d/%m/%Y','%d-%m-%Y'])]:
        match=re.search(p,text)
        if match:
            for fmt in formats:
                try: dt=datetime.strptime(match.group(),fmt).date().isoformat(); break
                except ValueError: pass
    return dict(merchant=merchant,amount=amount,date=dt,category=classify(merchant+' '+text)['category'],source=source,text=text,notice='Review all extracted fields before saving. Missing dates default to today. Supports debit SMS and INR receipt totals; refunds/credits need manual review.')
def budget_summary(income,rows,start,end):
    totals={k:0 for k in CATEGORIES}
    for t in rows: totals[t['category']]+=t['amount']
    pools={p:sum(totals[c] for c in CATEGORIES if CATEGORIES[c]==p) for p in ['Needs','Wants','Savings']}
    base={'Needs':income*.5,'Wants':income*.3,'Savings':income*.2}
    # Protect the savings target; finance essential overruns from unspent wants only.
    shift=min(max(0,pools['Needs']-base['Needs']),max(0,base['Wants']-pools['Wants']))
    adjusted={'Needs':base['Needs']+shift,'Wants':base['Wants']-shift,'Savings':base['Savings']}
    today=date.today(); days=(end-start).days
    elapsed=days if today>=end else max(1,(today-start).days+1)
    spent=pools['Needs']+pools['Wants']; saved=pools['Savings']; remaining=income-spent-saved
    recommendations=[]
    if income<=0: recommendations.append(dict(title='Set your monthly income',detail='Add your income to calculate budget envelopes and pacing.',kind='info'))
    else:
        if shift: recommendations.append(dict(title='Budget rebalanced',detail=f'₹{shift:,.0f} moved from available Wants to Needs. Your savings target stays protected.',kind='info'))
        for p in ['Needs','Wants']:
            if pools[p]>adjusted[p]: recommendations.append(dict(title=f'{p} budget exceeded',detail=f'You are ₹{pools[p]-adjusted[p]:,.0f} above the adjusted allocation.',kind='warning'))
            elif today>=start and today<end and pools[p]/elapsed*days>adjusted[p]: recommendations.append(dict(title=f'{p} spending is ahead of pace',detail=f'At this pace, month-end spending could reach ₹{pools[p]/elapsed*days:,.0f}.',kind='warning'))
        gap=max(0,base['Savings']-saved)
        recommendations.append(dict(title='Your savings target',detail=f'₹{gap:,.0f} left to reach your 20% goal.' if gap else 'You have reached your 20% savings goal.',kind='info'))
        if remaining<0: recommendations.append(dict(title='Income fully allocated',detail=f'Expenses and savings exceed income by ₹{-remaining:,.0f}. Review your transactions.',kind='warning'))
        if not rows: recommendations.append(dict(title='Start with one expense',detail='Add an expense, paste a debit SMS, or scan a receipt to build your spending picture.',kind='info'))
    daily={}
    for t in rows:
        if t['category']!='Savings': daily[t['date']]=round(daily.get(t['date'],0)+t['amount'],2)
    return dict(income=income,spent=round(spent,2),saved=round(saved,2),remaining=round(remaining,2),base=base,adjusted=adjusted,pools=pools,categories=totals,daily=daily,recommendations=recommendations,days=days,elapsed=elapsed)
