from flask import Flask, request, render_template, redirect, session, url_for
from pymongo import MongoClient
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.secret_key = "hello"

client = MongoClient("mongodb://localhost:27017/")
db = client["mydatabase"]
collection = db["items"]
students = db["student"]
available = db["available"]
counter = db["counter"]
code = db["passwords"]

FOOD_ITEMS = [
    ("samosa", 13), ("coke", 20), ("puff", 13), ("biscuit", 5),
    ("idli", 7), ("dosa", 10), ("poori", 10), ("meals", 35), ("variety_rice", 30)
]


def reset_menu():
    available.update_many({}, {"$set": {item: 0 for item, _ in FOOD_ITEMS}}, upsert=True)


def breakfast():
    available.update_many({}, {"$set": {"idli": 0, "dosa": 0, "poori": 0}}, upsert=True)


scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
scheduler.add_job(func=reset_menu, trigger="cron", hour=0, minute=0)
scheduler.add_job(func=breakfast, trigger="cron", hour=10, minute=0)
scheduler.start()


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        name = request.form['user']
        p = request.form['pass']
        if name == 'Raja' and p == 'raj1234':
            session['ownername'] = name
            return redirect(url_for('owner'))
        user = students.find_one({"Name": name, "Pass": p})
        if user:
            session['user'] = name
            return redirect(url_for('index'))
    return render_template('login.html')


@app.route('/forgot')
def forgot():
    return render_template('forgot.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if not code.find_one({"_id": "pass"}):
        code.insert_one({"_id": "pass", "host": '1975', "subhost": '2005'})

    if request.method == 'POST':
        if request.form['method'] == "Sign-up":
            c = code.find_one({"_id": "pass"})
            if request.form['code'] == c["subhost"] or request.form['code'] == c["host"]:
                students.insert_one({"Name": request.form['username'], "Pass": request.form['pass1']})
                return redirect(url_for('login'))
            else:
                return "Invalid code"
        if request.form['method'] == 'Change code':
            return redirect(url_for('codechange'))
    return render_template('register.html')


@app.route('/codechange', methods=['GET', 'POST'])
def codechange():
    if request.method == 'POST':
        c = code.find_one({"_id": "pass"})
        if request.form['host'] == c["host"]:
            code.update_one({"_id": "pass"}, {"$set": {"subhost": request.form['subhost']}})
            return "Subhost code changed successfully"
        else:
            return "Please enter correct code"
    return render_template('codechange.html')


@app.route('/index', methods=['GET', 'POST'])
def index():
    items = list(collection.find({}))
    ordered = {item: sum(doc.get(item, 0) for doc in items) for item, _ in FOOD_ITEMS}

    avl_data = list(available.find({}))
    avl = {item: int(avl_data[0].get(item, 0)) if avl_data else 0 for item, _ in FOOD_ITEMS}
    stock = {item: avl[item] - ordered.get(item, 0) for item, _ in FOOD_ITEMS}

    menu = {
        "Breakfast": [
            {"name": "idli", "price": 7, "image": "idli.jpg", "stock": stock["idli"]},
            {"name": "dosa", "price": 10, "image": "dosa.jpeg", "stock": stock["dosa"]},
            {"name": "poori", "price": 10, "image": "poori.jpg", "stock": stock["poori"]}
        ],
        "Break Time": [
            {"name": "samosa", "price": 13, "image": "samosa.jpg", "stock": stock["samosa"]},
            {"name": "coke", "price": 20, "image": "coke.jpeg", "stock": stock["coke"]},
            {"name": "puff", "price": 13, "image": "puff.jpg", "stock": stock["puff"]},
            {"name": "biscuit", "price": 5, "image": "bis.jpeg", "stock": stock["biscuit"]}
        ],
        "Lunch": [
            {"name": "meals", "price": 35, "image": "meals.jpeg", "stock": stock["meals"]},
            {"name": "variety_rice", "price": 30, "image": "veriety.jpeg", "stock": stock["variety_rice"]}
        ]
    }

    if request.method == 'POST':
        for item, _ in FOOD_ITEMS:
            session[item.capitalize()] = int(request.form.get(item, 0))
        return redirect(url_for('bill'))

    return render_template('index.html', user=session['user'], menu=menu)


@app.route('/bill', methods=['GET', 'POST'])
def bill():
    if request.method == 'POST':
        t = datetime.now().strftime('%Y-%m-%d  -  %H:%M:%S')
        today_str = datetime.now().strftime('%d-%m-%Y')
        count = counter.find_one({"_id": "daily_counter"})
        if count['last_reset'] != today_str:
            counter.update_one({"_id": "daily_counter"}, {"$set": {"count": 0, "last_reset": today_str}})
            count['count'] = 0
        new_count = count['count'] + 1
        counter.update_one({"_id": "daily_counter"}, {"$set": {"count": new_count}})

        session['date'] = today_str
        session['order_no'] = new_count

        collection.insert_one({"name": session['user'], "order_time": t, **{item: session.get(item.capitalize(), 0) for item, _ in FOOD_ITEMS}})
        return redirect(url_for('finalbill'))

    f, q, p, total = [], [], [], 0
    for item, price in FOOD_ITEMS:
        qty = session.get(item.capitalize(), 0)
        if qty > 0:
            f.append(item.capitalize())
            q.append(qty)
            p.append(price)
            total += qty * price

    return render_template('bill.html', username=session['user'], items=f, quantity=q, price=p, a=len(f), sum=total)


@app.route('/finalbill', methods=['GET', 'POST'])
def finalbill():
    if request.method == 'POST':
        return redirect(url_for('index'))

    f, q, p, total = [], [], [], 0
    for item, price in FOOD_ITEMS:
        qty = session.get(item.capitalize(), 0)
        if qty > 0:
            f.append(item.capitalize())
            q.append(qty)
            p.append(price)
            total += qty * price

    return render_template('finalbill.html', username=session['user'], items=f, quantity=q, price=p, a=len(f), sum=total, Date=session['date'], order_no=session['order_no'])


@app.route('/owner', methods=['GET', 'POST'])
def owner():
    if request.method == 'POST':
        method = request.form.get('method')
        if method == 'Add':
            available.delete_many({})
            available.insert_one({item: int(request.form.get(item, 0)) for item, _ in FOOD_ITEMS})
        elif method == 'Delete All Details':
            collection.delete_many({})
        elif method == 'See Details':
            return redirect(url_for('details'))

    today = datetime.now().strftime('%d')
    items = list(collection.find({"$expr": {"$eq": [{"$substr": ["$order_time", 8, 2]}, today]}}))

    a = [sum(item.get(food, 0) for item in items) for food, _ in FOOD_ITEMS]
    return render_template('owner.html', items=items, a=a, owner=session['ownername'])


@app.route('/details')
def details():
    items = list(collection.find({}))
    return render_template('details.html', items=items)


if __name__ == '__main__':
    app.run(debug=True)
    