from flask import Flask, g, render_template, request, redirect, url_for, session
import sqlite3
import os

DB_PATH = 'shop.db'
app = Flask(__name__)
app.secret_key = 'replace-with-a-random-secret' 

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    if os.path.exists(DB_PATH):
        return
    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    # users, products, cart_items
    c.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            category TEXT,
            price REAL,
            description TEXT,
            image TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE cart_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id INTEGER,
            qty INTEGER DEFAULT 1,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
    ''')

    # простой SVG dataURI как изображение (чтобы не требовать файлов)
    def svg_data(name, color='cccccc'):
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="300" height="200">
  <rect width="100%" height="100%" fill="#{color}"/>
  <text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" font-size="20" fill="#000">{name}</text>
</svg>'''
        return 'data:image/svg+xml;utf8,' + svg

    products = [
        ('lace dress', 'dresses', 410.00, 'a silk dress with lace frills', svg_data('dress','ffd1dc')),
        ('dress with lace collar', 'dresses', 310.00, 'a cream-colored dress with a long hem', svg_data('dress', 'ffd1dc')),
        ('trousers and shirt with ribbons', 'sets', 210.00, 'summer set made of light fabric', svg_data('set', 'cfe8ff')),
        ('top and skirt', 'sets', 310.00, 'corset top and pleated skirt', svg_data('set','cfe8ff')),
        ('mini skirt with translucent lining', 'skirts', 150.00, 'beige skirt with an accent flower', svg_data('skirt', 'd6f5d6')),
        ('flower skirt', 'skirts', 210.00, 'skirt with sewn flowers', svg_data('skirt','d6f5d6')),
        ('shell pendant', 'accessories', 30.00, 'mother-of-pearl shell on a chain', svg_data('accessories', 'fff2b2'))
        ('hair clips', 'accessories', 50.00, 'hair decoration with crystal drops and pearls', svg_data('accessories','fff2b2')),
    ]
    c.executemany('INSERT INTO products (name, category, price, description, image) VALUES (?,?,?,?,?)', products)
    db.commit()
    db.close()

@app.route('/')
def index():
    db = get_db()
    cur = db.execute('SELECT * FROM products')
    products = cur.fetchall()
    return render_template('index.html', products=products)

@app.route('/catalog')
def catalog():
    db = get_db()
    cur = db.execute('SELECT * FROM products')
    products = cur.fetchall()
    # group by category simply for display
    cats = {}
    for p in products:
        cats.setdefault(p['category'], []).append(p)
    return render_template('catalog.html', cats=cats)

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form['user'].strip()
        password = request.form['password']
        if not username or not password:
            return render_template('register.html', error='enter your name and password')
        db = get_db()
        try:
            db.execute('INSERT INTO users (username,password) VALUES (?,?)', (username,password))
            db.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return render_template('register.html', error='this user already exists')
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['user'].strip()
        password = request.form['password']
        db = get_db()
        cur = db.execute('SELECT * FROM users WHERE username=? AND password=?', (username,password))
        user = cur.fetchone()
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='incorrect data')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    product_id = int(request.form['product_id'])
    db = get_db()
    # если товар уже в корзине
    cur = db.execute('SELECT * FROM cart_items WHERE user_id=? AND product_id=?', (user_id,product_id))
    row = cur.fetchone()
    if row:
        db.execute('UPDATE cart_items SET qty=qty+1 WHERE id=?', (row['id'],))
    else:
        db.execute('INSERT INTO cart_items (user_id, product_id, qty) VALUES (?,?,1)', (user_id,product_id))
    db.commit()
    return redirect(url_for('catalog'))

@app.route('/cart')
def cart():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    db = get_db()
    cur = db.execute('''
        SELECT ci.id as cid, p.*, ci.qty
        FROM cart_items ci
        JOIN products p ON p.id = ci.product_id
        WHERE ci.user_id=?
    ''', (user_id,))
    items = cur.fetchall()
    total = sum(item['price'] * item['qty'] for item in items)
    return render_template('cart.html', items=items, total=total)

@app.route('/remove_from_cart', methods=['POST'])
def remove_from_cart():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    cid = int(request.form['cid'])
    db = get_db()
    db.execute('DELETE FROM cart_items WHERE id=?', (cid,))
    db.commit()
    return redirect(url_for('cart'))

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contacts')
def contacts():
    return render_template('contacts.html')

@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    products = []
    if query:
        db = get_db()
        cur = db.execute("SELECT * FROM products WHERE name LIKE ?", ('%' + query + '%',))
        products = cur.fetchall()
    return render_template('search.html', products=products, query=query)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)